"""Integration tests for the ML API endpoints.

Tests run against the real ML pipeline (no mocks) to exercise the full
request → schema validation → ML function → response serialisation chain.
Small synthetic datasets are used to keep runtime under a few seconds.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


# ---------------------------------------------------------------------------
# Fixtures & shared payloads
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def _hte_body(n: int = 120, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    x0 = rng.standard_normal(n).tolist()
    x1 = rng.standard_normal(n).tolist()
    treatment = (rng.random(n) < 0.5).astype(float).tolist()
    outcome = [
        0.3 * x0[i] + treatment[i] * (0.4 + 0.8 * x0[i]) + rng.standard_normal()
        for i in range(n)
    ]
    return {
        "features": [{"x0": x0[i], "x1": x1[i]} for i in range(n)],
        "treatment": treatment,
        "outcome": outcome,
        "random_state": 42,
        "bootstrap": False,
    }


def _segments_body(n_per_cluster: int = 80, seed: int = 1) -> dict:
    rng = np.random.default_rng(seed)
    features, treatment, outcome = [], [], []
    for cluster_idx, (cx, cy, lift) in enumerate([(0, 0, 0.1), (5, 0, 0.7), (2.5, 5, 0.4)]):
        x0 = rng.normal(cx, 0.4, n_per_cluster).tolist()
        x1 = rng.normal(cy, 0.4, n_per_cluster).tolist()
        t = (rng.random(n_per_cluster) < 0.5).astype(float).tolist()
        y = [x0[i] * 0.1 + t[i] * lift + rng.standard_normal() * 0.2 for i in range(n_per_cluster)]
        features += [{"x0": x0[i], "x1": x1[i]} for i in range(n_per_cluster)]
        treatment += t
        outcome += y
    return {
        "features": features,
        "treatment": treatment,
        "outcome": outcome,
        "max_k": 5,
        "random_state": 42,
    }


def _validate_body(n_days: int = 21, seed: int = 2) -> dict:
    rng = np.random.default_rng(seed)
    import pandas as pd
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    return {
        "daily_metrics": [
            {
                "date": str(dates[i].date()),
                "control_metric": float(rng.normal(0.30, 0.01)),
                "treatment_metric": float(rng.normal(0.33, 0.01)),
                "n_control": float(rng.integers(450, 550)),
                "n_treatment": float(rng.integers(450, 550)),
            }
            for i in range(n_days)
        ],
        "expected_ratio": 0.5,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/ml/hte — happy path
# ---------------------------------------------------------------------------


class TestHTE:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/ml/hte", json=_hte_body())
        assert r.status_code == 200, r.text

    def test_response_envelope(self, client: TestClient) -> None:
        body = client.post("/api/v1/ml/hte", json=_hte_body()).json()
        assert "data" in body
        assert "meta" in body

    def test_data_fields_present(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/hte", json=_hte_body()).json()["data"]
        for field in ("ate", "stability_score", "top_interactions",
                      "business_recommendation", "ite_point", "ite_uncertainty"):
            assert field in data, f"Missing field: {field}"

    def test_ite_point_length_matches_input(self, client: TestClient) -> None:
        body = _hte_body(n=120)
        data = client.post("/api/v1/ml/hte", json=body).json()["data"]
        assert len(data["ite_point"]) == 120

    def test_ite_uncertainty_zeros_when_bootstrap_false(self, client: TestClient) -> None:
        body = _hte_body()
        body["bootstrap"] = False
        data = client.post("/api/v1/ml/hte", json=body).json()["data"]
        assert all(v == 0.0 for v in data["ite_uncertainty"])

    def test_top_interactions_are_interaction_columns(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/hte", json=_hte_body()).json()["data"]
        for name in data["top_interactions"]:
            assert name.endswith("_x_treat"), f"Unexpected interaction name: {name}"

    def test_recommendation_is_nonempty(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/hte", json=_hte_body()).json()["data"]
        assert isinstance(data["business_recommendation"], str)
        assert len(data["business_recommendation"]) > 0

    # Error paths

    def test_mismatched_lengths_returns_422(self, client: TestClient) -> None:
        body = _hte_body()
        body["treatment"] = body["treatment"][:-1]  # one shorter
        r = client.post("/api/v1/ml/hte", json=body)
        assert r.status_code == 422

    def test_non_binary_treatment_returns_422(self, client: TestClient) -> None:
        body = _hte_body()
        body["treatment"][0] = 0.5
        r = client.post("/api/v1/ml/hte", json=body)
        assert r.status_code == 422

    def test_empty_features_returns_422(self, client: TestClient) -> None:
        body = _hte_body()
        body["features"] = []
        body["treatment"] = []
        body["outcome"] = []
        r = client.post("/api/v1/ml/hte", json=body)
        assert r.status_code == 422

    def test_extreme_imbalance_returns_400(self, client: TestClient) -> None:
        """< 10% treatment → ML layer raises ValueError → 400."""
        rng = np.random.default_rng(9)
        n = 200
        body = {
            "features": [{"x": float(v)} for v in rng.standard_normal(n)],
            "treatment": ([1.0] * 5 + [0.0] * 195),
            "outcome": rng.standard_normal(n).tolist(),
        }
        r = client.post("/api/v1/ml/hte", json=body)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/ml/segments — happy path
# ---------------------------------------------------------------------------


class TestSegments:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/ml/segments", json=_segments_body())
        assert r.status_code == 200, r.text

    def test_response_envelope(self, client: TestClient) -> None:
        body = client.post("/api/v1/ml/segments", json=_segments_body()).json()
        assert "data" in body
        assert "meta" in body

    def test_data_fields_present(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        for field in ("optimal_k", "silhouette_score", "segments",
                      "responsive_segments", "stability_scores",
                      "overall_recommendation", "low_confidence"):
            assert field in data, f"Missing field: {field}"

    def test_number_of_segments_equals_optimal_k(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        assert len(data["segments"]) == data["optimal_k"]

    def test_segment_ids_contiguous(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        ids = sorted(s["id"] for s in data["segments"])
        assert ids == list(range(data["optimal_k"]))

    def test_size_pcts_sum_to_one(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        total = sum(s["size_pct"] for s in data["segments"])
        assert abs(total - 1.0) < 1e-5

    def test_stability_scores_keys_are_strings(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        for key in data["stability_scores"]:
            assert isinstance(key, str)

    def test_three_cluster_data_finds_k_three(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        assert data["optimal_k"] == 3

    def test_top_features_values_are_two_element_lists(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        for seg in data["segments"]:
            for val in seg["top_features"].values():
                assert isinstance(val, list)
                assert len(val) == 2

    def test_overall_recommendation_nonempty(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/segments", json=_segments_body()).json()["data"]
        assert len(data["overall_recommendation"]) > 0

    # Error paths

    def test_mismatched_lengths_returns_422(self, client: TestClient) -> None:
        body = _segments_body()
        body["outcome"] = body["outcome"][:-1]
        r = client.post("/api/v1/ml/segments", json=body)
        assert r.status_code == 422

    def test_max_k_out_of_range_returns_422(self, client: TestClient) -> None:
        body = _segments_body()
        body["max_k"] = 1
        r = client.post("/api/v1/ml/segments", json=body)
        assert r.status_code == 422

    def test_empty_input_returns_422(self, client: TestClient) -> None:
        body = _segments_body()
        body["features"] = []
        body["treatment"] = []
        body["outcome"] = []
        r = client.post("/api/v1/ml/segments", json=body)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/ml/validate — happy path
# ---------------------------------------------------------------------------


class TestValidate:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/ml/validate", json=_validate_body())
        assert r.status_code == 200, r.text

    def test_response_envelope(self, client: TestClient) -> None:
        body = client.post("/api/v1/ml/validate", json=_validate_body()).json()
        assert "data" in body
        assert "meta" in body

    def test_data_fields_present(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        for field in ("overall_validity", "checks", "recommendation", "can_trust_results"):
            assert field in data, f"Missing field: {field}"

    def test_clean_data_is_valid(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        assert data["overall_validity"] == "VALID"

    def test_clean_data_can_trust_results(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        assert data["can_trust_results"] is True

    def test_returns_four_checks(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        names = {c["name"] for c in data["checks"]}
        assert names == {"srm_check", "outlier_days", "cusum_drift", "volume_spike"}

    def test_each_check_has_required_fields(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        for check in data["checks"]:
            for field in ("name", "passed", "score", "severity", "description", "action"):
                assert field in check, f"Check missing field {field}: {check}"

    def test_validity_is_one_of_three_values(self, client: TestClient) -> None:
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        assert data["overall_validity"] in {"VALID", "WARNING", "INVALID"}

    def test_recommendation_is_one_of_three_strings(self, client: TestClient) -> None:
        valid_recs = {
            "Results are valid. Proceed with analysis.",
            "Proceed with caution. Review flagged issues before acting on results.",
            "Do not trust these results. Investigate data pipeline before continuing.",
        }
        data = client.post("/api/v1/ml/validate", json=_validate_body()).json()["data"]
        assert data["recommendation"] in valid_recs

    def test_srm_drift_returns_invalid(self, client: TestClient) -> None:
        """60/40 assignment split should trigger SRM → INVALID."""
        rng = np.random.default_rng(5)
        import pandas as pd
        dates = pd.date_range("2024-01-01", periods=21, freq="D")
        body = {
            "daily_metrics": [
                {
                    "date": str(dates[i].date()),
                    "control_metric": float(rng.normal(0.30, 0.01)),
                    "treatment_metric": float(rng.normal(0.30, 0.01)),
                    "n_control": float(rng.integers(580, 620)),
                    "n_treatment": float(rng.integers(380, 420)),
                }
                for i in range(21)
            ],
            "expected_ratio": 0.5,
        }
        data = client.post("/api/v1/ml/validate", json=body).json()["data"]
        assert data["overall_validity"] == "INVALID"
        assert data["can_trust_results"] is False

    # Error paths

    def test_fewer_than_7_days_returns_422(self, client: TestClient) -> None:
        body = _validate_body(n_days=6)
        r = client.post("/api/v1/ml/validate", json=body)
        assert r.status_code == 422

    def test_zero_n_control_returns_422(self, client: TestClient) -> None:
        body = _validate_body()
        body["daily_metrics"][0]["n_control"] = 0
        r = client.post("/api/v1/ml/validate", json=body)
        assert r.status_code == 422

    def test_expected_ratio_out_of_range_returns_422(self, client: TestClient) -> None:
        body = _validate_body()
        body["expected_ratio"] = 1.1
        r = client.post("/api/v1/ml/validate", json=body)
        assert r.status_code == 422

    def test_missing_date_field_returns_422(self, client: TestClient) -> None:
        body = _validate_body()
        del body["daily_metrics"][0]["date"]
        r = client.post("/api/v1/ml/validate", json=body)
        assert r.status_code == 422

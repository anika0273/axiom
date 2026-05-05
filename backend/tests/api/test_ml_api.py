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


# ===========================================================================
# Shared helpers for DB-dependent tests
# ===========================================================================

# ---------------------------------------------------------------------------
# FakeAsyncSession — in-memory async session for tests that need DB operations
# ---------------------------------------------------------------------------


class _FakeResult:
    """Mimics SQLAlchemy CursorResult well enough for the repos."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list:
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0] if self._rows else 0

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeAsyncSession:
    """Minimal async session backed by in-memory dicts.

    Supports the exact SQLAlchemy operations used by the repositories:
      add / flush / commit / rollback / refresh / get / execute.
    """

    def __init__(self) -> None:
        self._exps: dict = {}    # str(UUID) → Experiment
        self._results: dict = {}  # str(UUID) → ExperimentResult

    # ── Mutation helpers ──────────────────────────────────────────────────

    def add(self, obj) -> None:
        from datetime import datetime, timezone
        from uuid import uuid4

        from app.models.experiment import Experiment, ExperimentResult

        if not getattr(obj, "id", None):
            obj.id = uuid4()
        now = datetime.now(timezone.utc)
        for attr in ("created_at", "updated_at", "analyzed_at"):
            if hasattr(obj, attr) and not getattr(obj, attr, None):
                setattr(obj, attr, now)

        if isinstance(obj, Experiment):
            self._exps[str(obj.id)] = obj
        elif isinstance(obj, ExperimentResult):
            self._results[str(obj.id)] = obj

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj) -> None:
        pass

    # ── Query helpers ─────────────────────────────────────────────────────

    async def get(self, cls, pk):
        from app.models.experiment import Experiment, ExperimentResult

        if cls is Experiment:
            return self._exps.get(str(pk))
        if cls is ExperimentResult:
            return self._results.get(str(pk))
        return None

    async def execute(self, stmt) -> _FakeResult:
        from app.models.experiment import Experiment, ExperimentResult

        # Determine the target table from stmt.froms (SQLAlchemy 2.x-safe).
        try:
            froms = list(stmt.froms)
        except (AttributeError, TypeError):
            return _FakeResult([0])

        if not froms:
            return _FakeResult([0])

        table_name = getattr(froms[0], "name", None)

        # Distinguish model-select vs. count/scalar by inspecting selected_columns.
        # For model queries the first selected column belongs to the model table;
        # for count queries it is a Function object with no .table attribute.
        try:
            first_selected = list(stmt.selected_columns)[0]
            is_model_query = (
                hasattr(first_selected, "table")
                and getattr(first_selected.table, "name", None) == table_name
            )
        except (AttributeError, IndexError, TypeError):
            is_model_query = False

        if not is_model_query:
            # Count / scalar query — return the row count of the relevant table.
            if table_name == "experiments":
                return _FakeResult([len(self._exps)])
            if table_name == "experiment_results":
                return _FakeResult([len(self._results)])
            return _FakeResult([0])

        # Model query — return matching rows.
        # Note: .first() vs .all() on _FakeResult handles LIMIT at the caller.
        if table_name == "experiments":
            rows = sorted(self._exps.values(), key=lambda e: e.created_at, reverse=True)
            return _FakeResult(rows)

        if table_name == "experiment_results":
            rows = list(self._results.values())
            exp_id = self._extract_where_value(stmt, "experiment_id")
            if exp_id is not None:
                rows = [r for r in rows if str(r.experiment_id) == str(exp_id)]
            rows.sort(key=lambda r: r.analyzed_at, reverse=True)
            return _FakeResult(rows)

        return _FakeResult([])

    def _extract_where_value(self, stmt, col_name: str):
        """Pull the bind-parameter value from a simple col == :val WHERE clause."""
        try:
            wc = stmt.whereclause
            if wc is None:
                return None
            left, right = wc.left, wc.right
            if getattr(left, "key", None) == col_name:
                return getattr(right, "value", None)
            if getattr(right, "key", None) == col_name:
                return getattr(left, "value", None)
        except (AttributeError, TypeError):
            pass
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_EXPERIMENT_CREATE_BODY = {
    "name": "Checkout button colour",
    "description": "Test blue vs green button",
    "experiment_type": "proportion",
    "baseline_metric": 0.05,
    "mde": 0.01,
    "alpha": 0.05,
    "power": 0.80,
}


def _analyze_body_minimal() -> dict:
    rng = np.random.default_rng(99)
    return {
        "control_values": rng.standard_normal(50).tolist(),
        "treatment_values": (rng.standard_normal(50) + 0.5).tolist(),
    }


@pytest.fixture()
def db_client():
    """TestClient whose get_db dependency yields a fresh FakeAsyncSession.

    Returns (client, fake_session) so tests can inspect stored state.
    """
    from app.dependencies import get_db
    from app.main import create_app

    fake = FakeAsyncSession()

    async def _override():
        yield fake

    app = create_app()
    app.dependency_overrides[get_db] = _override
    client = TestClient(app, raise_server_exceptions=False)
    yield client, fake
    app.dependency_overrides.clear()


# ===========================================================================
# POST /api/v1/ml/analyze
# ===========================================================================


class TestAnalyze:
    def test_happy_path_minimal(self, db_client) -> None:
        """Minimal request (only control/treatment) returns 200 with correct envelope."""
        client, _ = db_client
        r = client.post("/api/v1/ml/analyze", json=_analyze_body_minimal())
        assert r.status_code == 200, r.text
        body = r.json()
        assert "data" in body
        assert "meta" in body

    def test_response_fields_present(self, db_client) -> None:
        client, _ = db_client
        data = client.post("/api/v1/ml/analyze", json=_analyze_body_minimal()).json()["data"]
        for field in (
            "overall_verdict",
            "key_insights",
            "capability_report",
            "can_trust_results",
            "recommendation",
        ):
            assert field in data, f"Missing field: {field}"

    def test_verdict_is_valid_value(self, db_client) -> None:
        client, _ = db_client
        data = client.post("/api/v1/ml/analyze", json=_analyze_body_minimal()).json()["data"]
        assert data["overall_verdict"] in {"CLEAN", "NEEDS_REVIEW", "INVALID"}

    def test_no_optional_fields_modules_skipped(self, db_client) -> None:
        """With no user_features or daily_metrics all four modules are skipped."""
        client, _ = db_client
        data = client.post("/api/v1/ml/analyze", json=_analyze_body_minimal()).json()["data"]
        statuses = {s["module"]: s["status"] for s in data["capability_report"]}
        for module in ("hte", "segments", "anomaly", "novelty"):
            assert statuses[module] == "skipped", f"{module} should be skipped"

    def test_with_daily_metrics_anomaly_runs(self, db_client) -> None:
        """Providing daily_metrics causes anomaly module to run."""
        client, _ = db_client
        body = _analyze_body_minimal()
        body["daily_metrics"] = _validate_body(n_days=21)["daily_metrics"]
        data = client.post("/api/v1/ml/analyze", json=body).json()["data"]
        statuses = {s["module"]: s["status"] for s in data["capability_report"]}
        assert statuses["anomaly"] == "completed"

    def test_too_few_samples_returns_400(self, db_client) -> None:
        """Fewer than 10 samples per group triggers a 400."""
        client, _ = db_client
        body = {
            "control_values": [1.0] * 5,
            "treatment_values": [1.0] * 5,
        }
        r = client.post("/api/v1/ml/analyze", json=body)
        assert r.status_code in (400, 422)

    def test_with_experiment_id_stores_result(self, db_client) -> None:
        """When experiment_id is provided the result_id is returned."""
        client, fake = db_client
        import uuid
        exp_id = str(uuid.uuid4())
        body = _analyze_body_minimal()
        body["experiment_id"] = exp_id
        data = client.post("/api/v1/ml/analyze", json=body).json()["data"]
        assert data["result_id"] is not None
        assert data["experiment_id"] == exp_id
        # Fake session should now have one stored result.
        assert len(fake._results) == 1


# ===========================================================================
# GET /api/v1/ml/experiments/{id}/analysis
# ===========================================================================


class TestGetExperimentAnalysis:
    def test_not_found_returns_404(self, db_client) -> None:
        """No stored result → 404."""
        client, _ = db_client
        import uuid
        r = client.get(f"/api/v1/ml/experiments/{uuid.uuid4()}/analysis")
        assert r.status_code == 404

    def test_stored_result_returned(self, db_client) -> None:
        """After storing a result via analyze, the GET endpoint returns it."""
        client, fake = db_client
        import uuid
        exp_id = str(uuid.uuid4())
        body = _analyze_body_minimal()
        body["experiment_id"] = exp_id

        client.post("/api/v1/ml/analyze", json=body)

        r = client.get(f"/api/v1/ml/experiments/{exp_id}/analysis")
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["experiment_id"] == exp_id
        assert "overall_verdict" in data


# ===========================================================================
# POST /api/v1/experiments
# ===========================================================================


class TestCreateExperiment:
    def test_returns_201(self, db_client) -> None:
        client, _ = db_client
        r = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY)
        assert r.status_code == 201, r.text

    def test_response_envelope(self, db_client) -> None:
        client, _ = db_client
        body = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()
        assert "data" in body
        assert "meta" in body

    def test_returns_id(self, db_client) -> None:
        client, _ = db_client
        data = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()["data"]
        assert "id" in data
        import uuid
        uuid.UUID(data["id"])  # must be a valid UUID

    def test_status_is_draft(self, db_client) -> None:
        client, _ = db_client
        data = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()["data"]
        assert data["status"] == "draft"

    def test_experiment_type_echoed(self, db_client) -> None:
        client, _ = db_client
        data = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()["data"]
        assert data["experiment_type"] == "proportion"

    def test_missing_required_field_returns_422(self, db_client) -> None:
        client, _ = db_client
        bad = {k: v for k, v in _EXPERIMENT_CREATE_BODY.items() if k != "baseline_metric"}
        r = client.post("/api/v1/experiments", json=bad)
        assert r.status_code == 422

    def test_invalid_experiment_type_returns_422(self, db_client) -> None:
        client, _ = db_client
        bad = {**_EXPERIMENT_CREATE_BODY, "experiment_type": "banana"}
        r = client.post("/api/v1/experiments", json=bad)
        assert r.status_code == 422


# ===========================================================================
# GET /api/v1/experiments (list) and GET /api/v1/experiments/{id}
# ===========================================================================


class TestGetExperiment:
    def test_get_nonexistent_returns_404(self, db_client) -> None:
        client, _ = db_client
        import uuid
        r = client.get(f"/api/v1/experiments/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_get_created_experiment(self, db_client) -> None:
        client, _ = db_client
        created = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()["data"]
        r = client.get(f"/api/v1/experiments/{created['id']}")
        assert r.status_code == 200
        assert r.json()["data"]["id"] == created["id"]

    def test_list_returns_created_experiment(self, db_client) -> None:
        client, _ = db_client
        client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY)
        r = client.get("/api/v1/experiments")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "meta" in body
        assert len(body["data"]) >= 1

    def test_list_meta_fields(self, db_client) -> None:
        client, _ = db_client
        r = client.get("/api/v1/experiments")
        meta = r.json()["meta"]
        for field in ("total", "page", "page_size"):
            assert field in meta


# ===========================================================================
# PATCH /api/v1/experiments/{id}/status
# ===========================================================================


class TestUpdateStatus:
    def test_update_to_running(self, db_client) -> None:
        client, _ = db_client
        created = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()["data"]
        r = client.patch(
            f"/api/v1/experiments/{created['id']}/status",
            json={"status": "running"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "running"

    def test_nonexistent_returns_404(self, db_client) -> None:
        client, _ = db_client
        import uuid
        r = client.patch(
            f"/api/v1/experiments/{uuid.uuid4()}/status",
            json={"status": "running"},
        )
        assert r.status_code == 404

    def test_invalid_status_returns_422(self, db_client) -> None:
        client, _ = db_client
        created = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY).json()["data"]
        r = client.patch(
            f"/api/v1/experiments/{created['id']}/status",
            json={"status": "deleted"},
        )
        assert r.status_code == 422


# ===========================================================================
# Full round trip: create → analyze → retrieve
# ===========================================================================


class TestRoundTrip:
    def test_create_analyze_retrieve(self, db_client) -> None:
        """Create an experiment, run ML analysis against it, then retrieve the result."""
        client, _ = db_client

        # 1. Create experiment
        create_r = client.post("/api/v1/experiments", json=_EXPERIMENT_CREATE_BODY)
        assert create_r.status_code == 201, create_r.text
        exp_id = create_r.json()["data"]["id"]

        # 2. Run analysis with experiment_id
        analyze_body = _analyze_body_minimal()
        analyze_body["experiment_id"] = exp_id
        analyze_r = client.post("/api/v1/ml/analyze", json=analyze_body)
        assert analyze_r.status_code == 200, analyze_r.text
        analyze_data = analyze_r.json()["data"]
        assert analyze_data["experiment_id"] == exp_id
        assert analyze_data["result_id"] is not None

        # 3. Retrieve the stored analysis
        get_r = client.get(f"/api/v1/ml/experiments/{exp_id}/analysis")
        assert get_r.status_code == 200, get_r.text
        get_data = get_r.json()["data"]
        assert get_data["experiment_id"] == exp_id
        assert get_data["overall_verdict"] in {"CLEAN", "NEEDS_REVIEW", "INVALID"}
        assert isinstance(get_data["key_insights"], list)
        assert isinstance(get_data["can_trust_results"], bool)

        # 4. Experiment detail should show the latest result
        exp_r = client.get(f"/api/v1/experiments/{exp_id}")
        assert exp_r.status_code == 200
        exp_data = exp_r.json()["data"]
        assert exp_data["latest_result"] is not None
        assert exp_data["latest_result"]["overall_verdict"] in {"CLEAN", "NEEDS_REVIEW", "INVALID"}

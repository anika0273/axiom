"""Integration tests for the stats API endpoints.

Uses FastAPI's synchronous TestClient — no pytest-asyncio needed.
All tests run against the real stats engine (no mocks) so they also
exercise the computation layer end-to-end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Shared TestClient for the module; avoids re-creating the app per test."""
    return TestClient(create_app(), raise_server_exceptions=False)


# Reusable valid payloads ────────────────────────────────────────────────────

_SAMPLE_SIZE_BODY = {
    "baseline_rate": 0.05,
    "mde": 0.01,
    "alpha": 0.05,
    "power": 0.80,
}

_RUNTIME_BODY = {
    "required_sample_size": 3000,
    "daily_traffic": 500,
}

_ANALYZE_PROPORTION_BODY = {
    "config": {"test_type": "proportion", "alpha": 0.05, "power": 0.80},
    "data": {
        "control_n": 10000,
        "treatment_n": 10000,
        "control_success": 500,
        "treatment_success": 560,
    },
}

_ANALYZE_MEAN_BODY = {
    "config": {"test_type": "mean", "alpha": 0.05, "power": 0.80},
    "data": {
        "control_n": 50,
        "treatment_n": 50,
        "control_success": [float(i) for i in range(1, 51)],
        "treatment_success": [float(i) + 5.0 for i in range(1, 51)],
    },
}


# ---------------------------------------------------------------------------
# GET /api/v1/stats/health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/v1/stats/health")
        assert r.status_code == 200

    def test_response_envelope(self, client: TestClient) -> None:
        r = client.get("/api/v1/stats/health")
        body = r.json()
        assert "data" in body
        assert "meta" in body

    def test_data_fields(self, client: TestClient) -> None:
        data = client.get("/api/v1/stats/health").json()["data"]
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert isinstance(data["uptime"], float)
        assert data["uptime"] >= 0.0


# ---------------------------------------------------------------------------
# POST /api/v1/stats/power/sample-size
# ---------------------------------------------------------------------------


class TestSampleSize:
    def test_happy_path_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/stats/power/sample-size", json=_SAMPLE_SIZE_BODY)
        assert r.status_code == 200

    def test_response_has_required_fields(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/power/sample-size", json=_SAMPLE_SIZE_BODY
        ).json()["data"]
        assert "control_size" in data
        assert "treatment_size" in data
        assert "total_sample_size" in data
        assert "cohens_d" in data
        assert "power_curve" in data
        assert len(data["power_curve"]) > 0

    def test_control_equals_treatment_size(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/power/sample-size", json=_SAMPLE_SIZE_BODY
        ).json()["data"]
        assert data["control_size"] == data["treatment_size"]
        assert data["total_sample_size"] == data["control_size"] + data["treatment_size"]

    def test_missing_baseline_rate_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/stats/power/sample-size",
            json={"mde": 0.01, "alpha": 0.05, "power": 0.80},
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_alpha_out_of_range_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/stats/power/sample-size",
            json={**_SAMPLE_SIZE_BODY, "alpha": 0.0},
        )
        assert r.status_code == 422

    def test_zero_mde_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/stats/power/sample-size",
            json={**_SAMPLE_SIZE_BODY, "mde": 0.0},
        )
        assert r.status_code == 422

    def test_invalid_treatment_rate_returns_400(self, client: TestClient) -> None:
        # baseline_rate=0.99, mde=0.05 → treatment_rate=1.04 — invalid probability
        r = client.post(
            "/api/v1/stats/power/sample-size",
            json={**_SAMPLE_SIZE_BODY, "baseline_rate": 0.99, "mde": 0.05},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/stats/power/runtime
# ---------------------------------------------------------------------------


class TestRuntime:
    def test_happy_path_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/stats/power/runtime", json=_RUNTIME_BODY)
        assert r.status_code == 200

    def test_response_has_duration_fields(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/power/runtime", json=_RUNTIME_BODY
        ).json()["data"]
        assert "days_expected" in data
        assert "days_lower_95" in data
        assert "days_upper_95" in data
        assert "weeks_expected" in data

    def test_days_ordering(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/power/runtime", json=_RUNTIME_BODY
        ).json()["data"]
        assert data["days_lower_95"] <= data["days_expected"] <= data["days_upper_95"]

    def test_zero_daily_traffic_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/stats/power/runtime",
            json={"required_sample_size": 3000, "daily_traffic": 0},
        )
        assert r.status_code == 422

    def test_missing_body_returns_422(self, client: TestClient) -> None:
        r = client.post("/api/v1/stats/power/runtime", json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/stats/analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_proportion_happy_path_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/stats/analyze", json=_ANALYZE_PROPORTION_BODY)
        assert r.status_code == 200

    def test_proportion_response_has_recommendation(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/analyze", json=_ANALYZE_PROPORTION_BODY
        ).json()["data"]
        assert data["overall_recommendation"] in {"RUN", "STOP_WIN", "STOP_LOSE", "NO_EFFECT"}
        assert isinstance(data["plain_english"], str)
        assert len(data["plain_english"]) > 0

    def test_proportion_response_has_primary_result(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/analyze", json=_ANALYZE_PROPORTION_BODY
        ).json()["data"]
        pr = data["primary_result"]
        assert "is_significant" in pr
        assert "p_value" in pr
        assert "confidence_interval" in pr
        assert len(pr["confidence_interval"]) == 2

    def test_mean_happy_path_200(self, client: TestClient) -> None:
        r = client.post("/api/v1/stats/analyze", json=_ANALYZE_MEAN_BODY)
        assert r.status_code == 200

    def test_mean_response_test_type(self, client: TestClient) -> None:
        data = client.post(
            "/api/v1/stats/analyze", json=_ANALYZE_MEAN_BODY
        ).json()["data"]
        assert data["primary_result"]["test_type"] == "t-test"

    def test_wrong_success_type_returns_400(self, client: TestClient) -> None:
        # proportion test but list passed for control_success
        bad_body = {
            "config": {"test_type": "proportion"},
            "data": {
                "control_n": 100,
                "treatment_n": 100,
                "control_success": [0.1, 0.2, 0.3],  # should be int
                "treatment_success": 60,
            },
        }
        r = client.post("/api/v1/stats/analyze", json=bad_body)
        assert r.status_code in {400, 422}

    def test_missing_data_field_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/stats/analyze",
            json={"config": {"test_type": "proportion"}},  # no data field
        )
        assert r.status_code == 422

    def test_sequential_analysis(self, client: TestClient) -> None:
        body = {
            **_ANALYZE_PROPORTION_BODY,
            "config": {**_ANALYZE_PROPORTION_BODY["config"], "sequential_looks": 3},
            "current_look": 2,
        }
        r = client.post("/api/v1/stats/analyze", json=body)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["sequential_status"] is not None
        assert "decision" in data["sequential_status"]


# ---------------------------------------------------------------------------
# Headers — request ID, rate-limit, security
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_request_id_present_in_response(self, client: TestClient) -> None:
        r = client.get("/api/v1/stats/health")
        assert "x-request-id" in r.headers

    def test_custom_request_id_echoed_back(self, client: TestClient) -> None:
        custom_id = "test-request-abc-123"
        r = client.get("/api/v1/stats/health", headers={"X-Request-ID": custom_id})
        assert r.headers.get("x-request-id") == custom_id

    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        r = client.post("/api/v1/stats/power/sample-size", json=_SAMPLE_SIZE_BODY)
        assert r.status_code == 200
        # slowapi injects these on every response from a rate-limited endpoint
        assert "x-ratelimit-limit" in r.headers

    def test_security_headers_present(self, client: TestClient) -> None:
        r = client.get("/api/v1/stats/health")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("x-xss-protection") == "1; mode=block"

    def test_response_time_header_present(self, client: TestClient) -> None:
        r = client.get("/api/v1/stats/health")
        assert "x-response-time" in r.headers

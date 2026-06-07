"""Tests for POST /api/v1/experiments/{id}/analyze."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.main import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_experiment(
    experiment_id=None,
    exp_type="proportion",
    baseline_metric=0.05,
    mde=0.10,
    alpha=0.05,
    power=0.80,
    daily_traffic_estimate=500,
):
    """Return a MagicMock that quacks like an Experiment ORM row."""
    exp = MagicMock()
    exp.id = experiment_id or uuid.uuid4()
    exp.name = "Test Experiment"
    exp.description = None
    exp.hypothesis = None
    exp.baseline_metric = baseline_metric
    exp.mde = mde
    exp.alpha = alpha
    exp.power = power
    exp.daily_traffic_estimate = daily_traffic_estimate
    exp.experiment_type = MagicMock()
    exp.experiment_type.value = exp_type
    exp.status = MagicMock()
    exp.status.value = "running"
    exp.created_at = None
    exp.updated_at = None
    exp.started_at = None
    exp.completed_at = None
    return exp


def _make_metric(experiment_id):
    """Return a MagicMock that quacks like an ExperimentMetric ORM row."""
    m = MagicMock()
    m.experiment_id = experiment_id
    m.metric_name = "conversion_rate"
    m.is_primary = True
    m.metric_type = MagicMock()
    m.metric_type.value = "primary"
    return m


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """TestClient with get_db replaced by an AsyncMock session.

    The mock session's add / flush / refresh handle the result_repo.store_result
    call inside analysis_service without touching a real database.
    """
    app = create_app()

    async def _mock_get_db():
        session = AsyncMock()
        session.add = MagicMock()  # sync in SQLAlchemy
        yield session

    app.dependency_overrides[get_db] = _mock_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

_EXP_ID = uuid.uuid4()


class TestAnalyzeExperimentNotFound:
    def test_returns_404(self, client):
        from unittest.mock import patch

        with patch(
            "app.repositories.experiment_repo.get_experiment",
            new=AsyncMock(return_value=None),
        ):
            r = client.post(f"/api/v1/experiments/{_EXP_ID}/analyze")
        assert r.status_code == 404
        assert "not found" in r.json()["error"]["message"].lower()


class TestAnalyzeExperimentNoMetrics:
    def test_returns_422_when_no_metrics_configured(self, client):
        from unittest.mock import patch

        exp = _make_experiment(experiment_id=_EXP_ID)
        with (
            patch(
                "app.repositories.experiment_repo.get_experiment",
                new=AsyncMock(return_value=exp),
            ),
            patch(
                "app.repositories.experiment_repo.get_metrics",
                new=AsyncMock(return_value=[]),
            ),
        ):
            r = client.post(f"/api/v1/experiments/{_EXP_ID}/analyze")
        assert r.status_code == 422
        assert "no metrics" in r.json()["error"]["message"].lower()


class TestAnalyzeExperimentHappyPath:
    def _run(self, client, exp_type="proportion"):
        from unittest.mock import patch

        exp = _make_experiment(experiment_id=_EXP_ID, exp_type=exp_type)
        metric = _make_metric(_EXP_ID)
        with (
            patch(
                "app.repositories.experiment_repo.get_experiment",
                new=AsyncMock(return_value=exp),
            ),
            patch(
                "app.repositories.experiment_repo.get_metrics",
                new=AsyncMock(return_value=[metric]),
            ),
            patch(
                "app.repositories.subject_repo.has_subject_data",
                new=AsyncMock(return_value=False),
            ),
        ):
            return client.post(f"/api/v1/experiments/{_EXP_ID}/analyze")

    def test_proportion_returns_200(self, client):
        r = self._run(client, exp_type="proportion")
        assert r.status_code == 200, r.text

    def test_mean_returns_200(self, client):
        r = self._run(client, exp_type="mean")
        assert r.status_code == 200, r.text

    def test_response_has_data_envelope(self, client):
        r = self._run(client)
        body = r.json()
        assert "data" in body
        assert "meta" in body

    def test_response_data_has_stats(self, client):
        r = self._run(client)
        stats = r.json()["data"]["stats"]
        assert "primary_result" in stats
        assert "overall_recommendation" in stats
        assert stats["overall_recommendation"] in {
            "RUN",
            "STOP_WIN",
            "STOP_LOSE",
            "NO_EFFECT",
        }

    def test_response_data_has_ml(self, client):
        r = self._run(client)
        ml = r.json()["data"]["ml"]
        assert "overall_verdict" in ml
        assert ml["overall_verdict"] in {"CLEAN", "NEEDS_REVIEW", "INVALID"}
        assert "can_trust_results" in ml

    def test_response_data_has_experiment_id(self, client):
        r = self._run(client)
        assert r.json()["data"]["experiment_id"] == str(_EXP_ID)

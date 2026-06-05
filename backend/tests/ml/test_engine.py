"""Tests for backend/app/ml/engine.py — ML analysis orchestrator."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.ml.engine import MLAnalysisResult, MLExperimentInput, run_ml_analysis

# ---------------------------------------------------------------------------
# Synthetic data factories
# ---------------------------------------------------------------------------


def _make_input(
    n_ctrl: int = 60,
    n_trt: int = 60,
    seed: int = 0,
    with_features: bool = True,
    n_days: int = 21,
    with_daily: bool = True,
) -> MLExperimentInput:
    rng = np.random.default_rng(seed)
    ctrl = rng.normal(0.3, 0.05, n_ctrl).tolist()
    trt = rng.normal(0.35, 0.05, n_trt).tolist()

    features: pd.DataFrame | None = None
    if with_features:
        features = pd.DataFrame(
            {
                "x0": rng.standard_normal(n_ctrl + n_trt),
                "x1": rng.standard_normal(n_ctrl + n_trt),
            }
        )

    daily: pd.DataFrame | None = None
    if with_daily and n_days > 0:
        dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
        daily = pd.DataFrame(
            {
                "date": dates,
                "control_metric": rng.normal(0.30, 0.01, n_days),
                "treatment_metric": rng.normal(0.35, 0.01, n_days),
                "n_control": rng.integers(450, 550, n_days).astype(float),
                "n_treatment": rng.integers(450, 550, n_days).astype(float),
            }
        )

    return MLExperimentInput(
        control_values=ctrl,
        treatment_values=trt,
        user_features=features,
        daily_metrics=daily,
    )


def _minimal_input(n: int = 15, seed: int = 42) -> MLExperimentInput:
    """Bare minimum: just control and treatment values, no features or daily."""
    rng = np.random.default_rng(seed)
    return MLExperimentInput(
        control_values=rng.normal(0.3, 0.05, n).tolist(),
        treatment_values=rng.normal(0.35, 0.05, n).tolist(),
    )


# ---------------------------------------------------------------------------
# Full input — all modules should complete
# ---------------------------------------------------------------------------


class TestFullInput:
    def test_returns_analysis_result(self) -> None:
        result = run_ml_analysis(_make_input())
        assert isinstance(result, MLAnalysisResult)

    def test_capability_report_always_four_entries(self) -> None:
        result = run_ml_analysis(_make_input())
        assert len(result.capability_report) == 4

    def test_capability_report_covers_all_modules(self) -> None:
        result = run_ml_analysis(_make_input())
        names = {s.module for s in result.capability_report}
        assert names == {"hte", "segments", "anomaly", "novelty"}

    def test_verdict_is_valid_literal(self) -> None:
        result = run_ml_analysis(_make_input())
        assert result.overall_verdict in {"CLEAN", "NEEDS_REVIEW", "INVALID"}

    def test_key_insights_nonempty(self) -> None:
        result = run_ml_analysis(_make_input())
        assert len(result.key_insights) >= 1

    def test_key_insights_at_most_three(self) -> None:
        result = run_ml_analysis(_make_input())
        assert len(result.key_insights) <= 3

    def test_key_insights_no_empty_strings(self) -> None:
        result = run_ml_analysis(_make_input())
        for insight in result.key_insights:
            assert isinstance(insight, str) and len(insight) > 0

    def test_recommendation_is_nonempty_string(self) -> None:
        result = run_ml_analysis(_make_input())
        assert isinstance(result.recommendation, str) and len(result.recommendation) > 0

    def test_module_statuses_are_valid(self) -> None:
        result = run_ml_analysis(_make_input())
        for s in result.capability_report:
            assert s.status in {"completed", "skipped", "failed"}

    def test_duration_seconds_nonnegative(self) -> None:
        result = run_ml_analysis(_make_input())
        for s in result.capability_report:
            assert s.duration_seconds >= 0.0

    def test_all_modules_completed_on_full_data(self) -> None:
        result = run_ml_analysis(_make_input())
        for s in result.capability_report:
            assert (
                s.status == "completed"
            ), f"Module {s.module} did not complete: {s.status}"

    def test_anomaly_result_populated(self) -> None:
        result = run_ml_analysis(_make_input())
        assert result.anomaly_result is not None

    def test_novelty_result_populated(self) -> None:
        result = run_ml_analysis(_make_input())
        assert result.novelty_result is not None

    def test_hte_result_populated(self) -> None:
        result = run_ml_analysis(_make_input())
        assert result.hte_result is not None

    def test_segment_result_populated(self) -> None:
        result = run_ml_analysis(_make_input())
        assert result.segment_result is not None

    def test_can_trust_results_is_bool(self) -> None:
        result = run_ml_analysis(_make_input())
        assert isinstance(result.can_trust_results, bool)


# ---------------------------------------------------------------------------
# No user features — HTE + segments skipped
# ---------------------------------------------------------------------------


class TestNoUserFeatures:
    def test_hte_skipped(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        hte_status = next(s for s in result.capability_report if s.module == "hte")
        assert hte_status.status == "skipped"

    def test_segments_skipped(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        seg_status = next(s for s in result.capability_report if s.module == "segments")
        assert seg_status.status == "skipped"

    def test_anomaly_still_runs(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        anom = next(s for s in result.capability_report if s.module == "anomaly")
        assert anom.status == "completed"

    def test_novelty_still_runs(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        nov = next(s for s in result.capability_report if s.module == "novelty")
        assert nov.status == "completed"

    def test_hte_result_is_none(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        assert result.hte_result is None

    def test_segment_result_is_none(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        assert result.segment_result is None

    def test_skip_reason_mentions_features(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        hte_status = next(s for s in result.capability_report if s.module == "hte")
        assert hte_status.skip_reason is not None
        assert "features" in hte_status.skip_reason.lower()

    def test_still_has_four_capability_entries(self) -> None:
        result = run_ml_analysis(_make_input(with_features=False))
        assert len(result.capability_report) == 4


# ---------------------------------------------------------------------------
# No daily metrics — anomaly + novelty skipped
# ---------------------------------------------------------------------------


class TestNoDailyMetrics:
    def test_anomaly_skipped(self) -> None:
        result = run_ml_analysis(_make_input(with_daily=False))
        anom = next(s for s in result.capability_report if s.module == "anomaly")
        assert anom.status == "skipped"

    def test_novelty_skipped(self) -> None:
        result = run_ml_analysis(_make_input(with_daily=False))
        nov = next(s for s in result.capability_report if s.module == "novelty")
        assert nov.status == "skipped"

    def test_hte_still_runs(self) -> None:
        result = run_ml_analysis(_make_input(with_daily=False))
        hte_s = next(s for s in result.capability_report if s.module == "hte")
        assert hte_s.status == "completed"

    def test_segments_still_runs(self) -> None:
        result = run_ml_analysis(_make_input(with_daily=False))
        seg_s = next(s for s in result.capability_report if s.module == "segments")
        assert seg_s.status == "completed"

    def test_anomaly_result_is_none(self) -> None:
        result = run_ml_analysis(_make_input(with_daily=False))
        assert result.anomaly_result is None

    def test_novelty_result_is_none(self) -> None:
        result = run_ml_analysis(_make_input(with_daily=False))
        assert result.novelty_result is None


# ---------------------------------------------------------------------------
# No features AND no daily metrics — all modules skipped
# ---------------------------------------------------------------------------


class TestNoOptionalData:
    def test_no_crash(self) -> None:
        result = run_ml_analysis(_minimal_input())
        assert isinstance(result, MLAnalysisResult)

    def test_verdict_needs_review(self) -> None:
        result = run_ml_analysis(_minimal_input())
        assert result.overall_verdict == "NEEDS_REVIEW"

    def test_all_modules_skipped(self) -> None:
        result = run_ml_analysis(_minimal_input())
        for s in result.capability_report:
            assert s.status == "skipped", f"Expected {s.module} skipped, got {s.status}"

    def test_recommendation_mentions_insufficient(self) -> None:
        result = run_ml_analysis(_minimal_input())
        assert (
            "Insufficient" in result.recommendation
            or "data" in result.recommendation.lower()
        )

    def test_still_has_four_capability_entries(self) -> None:
        result = run_ml_analysis(_minimal_input())
        assert len(result.capability_report) == 4


# ---------------------------------------------------------------------------
# Minimum group size enforcement
# ---------------------------------------------------------------------------


def test_raises_when_control_too_small() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="10 users"):
        run_ml_analysis(
            MLExperimentInput(
                control_values=rng.standard_normal(5).tolist(),
                treatment_values=rng.standard_normal(20).tolist(),
            )
        )


def test_raises_when_treatment_too_small() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="10 users"):
        run_ml_analysis(
            MLExperimentInput(
                control_values=rng.standard_normal(20).tolist(),
                treatment_values=rng.standard_normal(3).tolist(),
            )
        )


def test_exactly_10_per_group_does_not_raise() -> None:
    rng = np.random.default_rng(0)
    result = run_ml_analysis(
        MLExperimentInput(
            control_values=rng.standard_normal(10).tolist(),
            treatment_values=rng.standard_normal(10).tolist(),
        )
    )
    assert isinstance(result, MLAnalysisResult)


# ---------------------------------------------------------------------------
# Fault isolation — one module failure must not block others
# ---------------------------------------------------------------------------


class TestFaultIsolation:
    def test_anomaly_failure_does_not_crash(self) -> None:
        inp = _make_input(with_features=False)  # skip HTE/segments for speed
        with patch(
            "app.ml.engine.validate_experiment", side_effect=RuntimeError("injected")
        ):
            result = run_ml_analysis(inp)
        assert isinstance(result, MLAnalysisResult)

    def test_anomaly_failure_recorded_as_failed(self) -> None:
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.validate_experiment", side_effect=RuntimeError("injected")
        ):
            result = run_ml_analysis(inp)
        anom = next(s for s in result.capability_report if s.module == "anomaly")
        assert anom.status == "failed"

    def test_anomaly_failure_records_exception_message(self) -> None:
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.validate_experiment", side_effect=RuntimeError("injected")
        ):
            result = run_ml_analysis(inp)
        anom = next(s for s in result.capability_report if s.module == "anomaly")
        assert anom.skip_reason is not None and "injected" in anom.skip_reason

    def test_novelty_failure_others_still_complete(self) -> None:
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.analyze_effect_trajectory", side_effect=ValueError("boom")
        ):
            result = run_ml_analysis(inp)
        nov = next(s for s in result.capability_report if s.module == "novelty")
        anom = next(s for s in result.capability_report if s.module == "anomaly")
        assert nov.status == "failed"
        assert anom.status == "completed"

    def test_module_failure_triggers_needs_review(self) -> None:
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.validate_experiment", side_effect=RuntimeError("injected")
        ):
            result = run_ml_analysis(inp)
        assert result.overall_verdict == "NEEDS_REVIEW"

    def test_hte_failure_segments_still_runs(self) -> None:
        inp = _make_input(with_daily=False)
        with patch("app.ml.engine.fit_hte_model", side_effect=ValueError("hte boom")):
            result = run_ml_analysis(inp)
        hte_s = next(s for s in result.capability_report if s.module == "hte")
        seg_s = next(s for s in result.capability_report if s.module == "segments")
        assert hte_s.status == "failed"
        assert seg_s.status == "completed"


# ---------------------------------------------------------------------------
# Parallel execution — HTE and segments run concurrently
# ---------------------------------------------------------------------------


class TestParallelExecution:
    def test_both_modules_called_when_features_provided(self) -> None:
        inp = _make_input(with_daily=False)
        with (
            patch("app.ml.engine.fit_hte_model") as mock_hte,
            patch("app.ml.engine.discover_segments") as mock_seg,
        ):
            mock_hte.return_value = MagicMock(
                spec=[
                    "ate",
                    "stability_score",
                    "top_interactions",
                    "business_recommendation",
                    "ite_point",
                    "ite_uncertainty",
                ]
            )
            mock_hte.return_value.top_interactions = ["x0_x_treat"]
            mock_hte.return_value.ate = 0.05
            mock_hte.return_value.stability_score = 0.9
            mock_hte.return_value.business_recommendation = "Target x0 users."
            mock_seg.return_value = MagicMock(
                spec=[
                    "optimal_k",
                    "silhouette_score",
                    "segments",
                    "responsive_segments",
                    "stability_scores",
                    "overall_recommendation",
                    "low_confidence",
                ]
            )
            mock_seg.return_value.responsive_segments = []
            mock_seg.return_value.optimal_k = 2
            mock_seg.return_value.overall_recommendation = "No clear segments."
            mock_seg.return_value.segments = []
            run_ml_analysis(inp)

        mock_hte.assert_called_once()
        mock_seg.assert_called_once()

    def test_hte_and_segments_run_concurrently(self) -> None:
        """Both functions must reach a threading.Barrier simultaneously.

        If the implementation were sequential, the first function would block
        at the barrier indefinitely (no second party arrives within timeout).
        """
        barrier = threading.Barrier(2, timeout=5)

        def mock_hte_fn(X, treatment, outcome, **kw):
            barrier.wait()
            m = MagicMock()
            m.top_interactions = []
            m.ate = 0.0
            m.stability_score = 0.5
            m.business_recommendation = "ok"
            return m

        def mock_seg_fn(X, treatment, outcome, **kw):
            barrier.wait()
            m = MagicMock()
            m.responsive_segments = []
            m.optimal_k = 2
            m.overall_recommendation = "ok"
            m.segments = []
            return m

        inp = _make_input(with_daily=False)
        with (
            patch("app.ml.engine.fit_hte_model", side_effect=mock_hte_fn),
            patch("app.ml.engine.discover_segments", side_effect=mock_seg_fn),
        ):
            result = run_ml_analysis(inp)

        # If we reach here both functions met at the barrier → ran concurrently.
        hte_s = next(s for s in result.capability_report if s.module == "hte")
        seg_s = next(s for s in result.capability_report if s.module == "segments")
        assert hte_s.status == "completed"
        assert seg_s.status == "completed"


# ---------------------------------------------------------------------------
# Verdict rules
# ---------------------------------------------------------------------------


class TestVerdictRules:
    def test_invalid_anomaly_gives_invalid_verdict(self) -> None:
        from app.ml.anomaly import ExperimentValidation, ValidationCheck

        invalid_validation = ExperimentValidation(
            overall_validity="INVALID",
            checks=[
                ValidationCheck("srm_check", False, 0.001, "critical", "SRM", "Fix it")
            ],
            recommendation="Do not trust these results. Investigate data pipeline before continuing.",
            can_trust_results=False,
        )
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.validate_experiment", return_value=invalid_validation
        ):
            result = run_ml_analysis(inp)
        assert result.overall_verdict == "INVALID"
        assert result.can_trust_results is False

    def test_invalid_verdict_gives_do_not_act_recommendation(self) -> None:
        from app.ml.anomaly import ExperimentValidation, ValidationCheck

        invalid_validation = ExperimentValidation(
            overall_validity="INVALID",
            checks=[
                ValidationCheck("srm_check", False, 0.001, "critical", "SRM", "Fix it")
            ],
            recommendation="Do not trust these results. Investigate data pipeline before continuing.",
            can_trust_results=False,
        )
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.validate_experiment", return_value=invalid_validation
        ):
            result = run_ml_analysis(inp)
        assert "Do not act" in result.recommendation

    def test_novelty_pattern_gives_needs_review(self) -> None:
        from app.ml.novelty import EffectTrajectory

        novelty_traj = EffectTrajectory(
            pattern="NOVELTY",
            slope=-0.008,
            slope_ci=(-0.012, -0.004),
            initial_lift=0.10,
            projected_stable_lift=0.01,
            days_to_stable=14,
            confidence="high",
            recommendation="Novelty effect detected. Wait 14 days for steady-state.",
        )
        inp = _make_input(with_features=False)
        with patch(
            "app.ml.engine.analyze_effect_trajectory", return_value=novelty_traj
        ):
            result = run_ml_analysis(inp)
        assert result.overall_verdict == "NEEDS_REVIEW"

    def test_clean_data_no_issues_gives_clean_verdict(self) -> None:
        # No daily data, no user features — but stable and passing modules.
        # Use mocked stable anomaly + stable novelty.
        from app.ml.anomaly import ExperimentValidation, ValidationCheck
        from app.ml.novelty import EffectTrajectory

        valid_anomaly = ExperimentValidation(
            overall_validity="VALID",
            checks=[ValidationCheck("srm_check", True, 0.8, "critical", "ok", "ok")],
            recommendation="Results are valid. Proceed with analysis.",
            can_trust_results=True,
        )
        stable_novelty = EffectTrajectory(
            pattern="STABLE",
            slope=0.0001,
            slope_ci=(-0.001, 0.001),
            initial_lift=0.05,
            projected_stable_lift=0.05,
            days_to_stable=0,
            confidence="high",
            recommendation="Effect is stable. Safe to make shipping decision.",
        )
        inp = _make_input(with_features=False)
        with (
            patch("app.ml.engine.validate_experiment", return_value=valid_anomaly),
            patch(
                "app.ml.engine.analyze_effect_trajectory", return_value=stable_novelty
            ),
        ):
            result = run_ml_analysis(inp)
        assert result.overall_verdict == "CLEAN"
        assert result.can_trust_results is True


# ---------------------------------------------------------------------------
# Key insights
# ---------------------------------------------------------------------------


class TestKeyInsights:
    def test_insights_from_completed_modules_only(self) -> None:
        # No daily metrics → anomaly + novelty skipped; insights from HTE + segments only.
        result = run_ml_analysis(_make_input(with_daily=False))
        assert len(result.key_insights) >= 1

    def test_no_insight_when_all_skipped(self) -> None:
        result = run_ml_analysis(_minimal_input())
        # No modules completed → no insights.
        assert len(result.key_insights) == 0

    def test_insights_are_strings(self) -> None:
        result = run_ml_analysis(_make_input())
        for insight in result.key_insights:
            assert isinstance(insight, str)

    def test_insights_not_empty_strings(self) -> None:
        result = run_ml_analysis(_make_input())
        for insight in result.key_insights:
            assert len(insight) > 0

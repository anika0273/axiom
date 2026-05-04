"""Tests for backend/app/ml/anomaly.py — experiment validity guardrails."""

from __future__ import annotations

import warnings
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.ml.anomaly import (
    ExperimentValidation,
    ValidationCheck,
    _aggregate_validity,
    check_cusum_drift,
    check_srm,
    check_volume_spike,
    detect_outlier_days,
    validate_experiment,
)


# ---------------------------------------------------------------------------
# Synthetic data factories
# ---------------------------------------------------------------------------


def _clean_daily(n_days: int = 28, seed: int = 0) -> pd.DataFrame:
    """Balanced, stationary experiment with no anomalies."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n_days, freq="D"),
        "control_metric": rng.normal(0.30, 0.01, n_days),
        "treatment_metric": rng.normal(0.33, 0.01, n_days),
        "n_control": rng.integers(450, 550, n_days).astype(float),
        "n_treatment": rng.integers(450, 550, n_days).astype(float),
    })


def _srm_daily(n_days: int = 28, seed: int = 1) -> pd.DataFrame:
    """60/40 assignment split (expected 50/50) → SRM."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n_days, freq="D"),
        "control_metric": rng.normal(0.30, 0.01, n_days),
        "treatment_metric": rng.normal(0.30, 0.01, n_days),
        "n_control": rng.integers(580, 620, n_days).astype(float),   # ~60%
        "n_treatment": rng.integers(380, 420, n_days).astype(float),  # ~40%
    })


def _bot_attack_daily(n_days: int = 28, seed: int = 2, attack_day: int = 10) -> pd.DataFrame:
    """One day has 10× normal volume — bot flood."""
    rng = np.random.default_rng(seed)
    n_ctrl = rng.integers(450, 550, n_days).astype(float)
    n_trt = rng.integers(450, 550, n_days).astype(float)
    n_ctrl[attack_day] *= 10
    n_trt[attack_day] *= 10
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n_days, freq="D"),
        "control_metric": rng.normal(0.30, 0.01, n_days),
        "treatment_metric": rng.normal(0.30, 0.01, n_days),
        "n_control": n_ctrl,
        "n_treatment": n_trt,
    })


def _cusum_drift_daily(n_days: int = 28, seed: int = 3) -> pd.DataFrame:
    """Metric gap grows steadily after day 10 — gradual divergence."""
    rng = np.random.default_rng(seed)
    ctrl = rng.normal(0.30, 0.005, n_days)
    trt = ctrl.copy()
    # Inject a linear upward drift starting at day 10.
    for i in range(10, n_days):
        trt[i] += (i - 10) * 0.015
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n_days, freq="D"),
        "control_metric": ctrl,
        "treatment_metric": trt,
        "n_control": rng.integers(450, 550, n_days).astype(float),
        "n_treatment": rng.integers(450, 550, n_days).astype(float),
    })


# ---------------------------------------------------------------------------
# Return-type and structure
# ---------------------------------------------------------------------------


def test_validate_experiment_returns_experiment_validation():
    result = validate_experiment(_clean_daily())
    assert isinstance(result, ExperimentValidation)


def test_validate_experiment_returns_four_checks():
    result = validate_experiment(_clean_daily())
    check_names = {c.name for c in result.checks}
    assert check_names == {"srm_check", "outlier_days", "cusum_drift", "volume_spike"}


def test_each_check_is_validation_check():
    result = validate_experiment(_clean_daily())
    for c in result.checks:
        assert isinstance(c, ValidationCheck)


def test_overall_validity_is_one_of_three_values():
    result = validate_experiment(_clean_daily())
    assert result.overall_validity in {"VALID", "WARNING", "INVALID"}


def test_recommendation_is_one_of_three_strings():
    valid_recs = {
        "Results are valid. Proceed with analysis.",
        "Proceed with caution. Review flagged issues before acting on results.",
        "Do not trust these results. Investigate data pipeline before continuing.",
    }
    result = validate_experiment(_clean_daily())
    assert result.recommendation in valid_recs


# ---------------------------------------------------------------------------
# Clean data → VALID
# ---------------------------------------------------------------------------


def test_clean_data_is_valid():
    result = validate_experiment(_clean_daily())
    assert result.overall_validity == "VALID"


def test_clean_data_can_trust_results():
    result = validate_experiment(_clean_daily())
    assert result.can_trust_results is True


def test_clean_data_all_checks_pass():
    result = validate_experiment(_clean_daily())
    failed = [c.name for c in result.checks if not c.passed]
    assert failed == [], f"Expected all checks to pass, but these failed: {failed}"


# ---------------------------------------------------------------------------
# SRM injection → SRM check fails (WARNING or INVALID)
# ---------------------------------------------------------------------------


def test_srm_injection_fails_srm_check():
    result = validate_experiment(_srm_daily())
    srm = next(c for c in result.checks if c.name == "srm_check")
    assert not srm.passed, "Expected SRM check to fail on 60/40 split"


def test_srm_is_always_critical_severity():
    result = validate_experiment(_srm_daily())
    srm = next(c for c in result.checks if c.name == "srm_check")
    assert srm.severity == "critical"


def test_srm_failure_makes_result_invalid():
    result = validate_experiment(_srm_daily())
    assert result.overall_validity == "INVALID"


def test_srm_failure_sets_can_trust_false():
    result = validate_experiment(_srm_daily())
    assert result.can_trust_results is False


def test_srm_uses_chi2_contingency():
    """SRM must delegate to scipy.stats.chi2_contingency."""
    n_control = pd.Series([600] * 20)
    n_treatment = pd.Series([400] * 20)
    with patch("app.ml.anomaly.chi2_contingency") as mock_chi2:
        mock_chi2.return_value = (10.0, 0.001, 1, np.array([[600, 400], [500, 500]]))
        check = check_srm(n_control, n_treatment)
        mock_chi2.assert_called_once()


def test_srm_passes_on_50_50():
    n_control = pd.Series([500] * 28)
    n_treatment = pd.Series([500] * 28)
    check = check_srm(n_control, n_treatment)
    assert check.passed


# ---------------------------------------------------------------------------
# Bot attack day → volume spike detected
# ---------------------------------------------------------------------------


def test_bot_attack_triggers_volume_spike():
    result = validate_experiment(_bot_attack_daily())
    spike = next(c for c in result.checks if c.name == "volume_spike")
    assert not spike.passed, "Expected volume_spike check to fail on bot attack day"


def test_bot_attack_spike_score_nonzero():
    result = validate_experiment(_bot_attack_daily())
    spike = next(c for c in result.checks if c.name == "volume_spike")
    assert spike.score > 0.0


def test_volume_spike_check_standalone():
    df = _bot_attack_daily(attack_day=5)
    check = check_volume_spike(df["n_control"], df["n_treatment"])
    assert not check.passed
    assert check.severity in {"warning", "critical"}


def test_volume_spike_no_attack_passes():
    df = _clean_daily()
    check = check_volume_spike(df["n_control"], df["n_treatment"])
    assert check.passed


def test_volume_spike_critical_above_20pct():
    """More than 20% spiked days → critical severity.

    Spikes must be placed AFTER the baseline window (first 20% = 4 days).
    If spiked days are inside the baseline, the baseline mean is inflated and
    the threshold rises with it, so nothing looks like a spike.
    """
    rng = np.random.default_rng(0)
    n_days = 20
    n_ctrl = rng.integers(100, 120, n_days).astype(float)
    n_trt = rng.integers(100, 120, n_days).astype(float)
    # Spike 6 days (30%) starting at day 5 — after the 4-day clean baseline.
    n_ctrl[5:11] *= 10
    n_trt[5:11] *= 10
    check = check_volume_spike(pd.Series(n_ctrl), pd.Series(n_trt))
    assert check.severity == "critical"


# ---------------------------------------------------------------------------
# CUSUM drift injection → drift check fires
# ---------------------------------------------------------------------------


def test_cusum_drift_fires_on_injected_drift():
    df = _cusum_drift_daily()
    check = check_cusum_drift(df["control_metric"], df["treatment_metric"])
    assert not check.passed, "Expected CUSUM drift to fire on injected divergence"


def test_cusum_drift_score_above_threshold_on_drifted_data():
    df = _cusum_drift_daily()
    # Use explicit low threshold so the score check is threshold-independent.
    check = check_cusum_drift(df["control_metric"], df["treatment_metric"], threshold=5.0)
    assert check.score > 5.0, f"Expected score > 5.0, got {check.score:.2f}"


def test_cusum_critical_on_two_crossings():
    """Two crossings → critical severity."""
    df = _cusum_drift_daily()
    check = check_cusum_drift(df["control_metric"], df["treatment_metric"], threshold=2.0)
    assert check.severity == "critical"


def test_cusum_passes_on_stationary_gap():
    rng = np.random.default_rng(42)
    n = 28
    ctrl = pd.Series(rng.normal(0.30, 0.005, n))
    trt = pd.Series(rng.normal(0.33, 0.005, n))  # constant offset, no drift
    check = check_cusum_drift(ctrl, trt)
    assert check.passed


def test_cusum_passes_on_flat_identical_series():
    ctrl = pd.Series([0.3] * 28)
    trt = pd.Series([0.3] * 28)
    check = check_cusum_drift(ctrl, trt)
    assert check.passed


# ---------------------------------------------------------------------------
# Minimum days enforcement
# ---------------------------------------------------------------------------


def test_raises_on_fewer_than_7_days():
    df = _clean_daily(n_days=6)
    with pytest.raises(ValueError, match="7 days"):
        validate_experiment(df)


def test_exactly_7_days_does_not_raise():
    df = _clean_daily(n_days=7)
    result = validate_experiment(df)
    assert isinstance(result, ExperimentValidation)


# ---------------------------------------------------------------------------
# Independence: one failing check must not block others
# ---------------------------------------------------------------------------


def test_all_checks_run_even_if_one_raises():
    """If one check function raises, the others must still run."""
    df = _clean_daily()

    with patch("app.ml.anomaly.check_srm", side_effect=RuntimeError("injected error")):
        result = validate_experiment(df)

    check_names = {c.name for c in result.checks}
    assert "srm_check" in check_names       # error captured as a failed check
    assert "outlier_days" in check_names    # still ran
    assert "cusum_drift" in check_names     # still ran
    assert "volume_spike" in check_names    # still ran
    assert len(result.checks) == 4


def test_erroring_check_is_marked_failed():
    df = _clean_daily()
    with patch("app.ml.anomaly.detect_outlier_days", side_effect=ValueError("boom")):
        result = validate_experiment(df)
    outlier_check = next(c for c in result.checks if c.name == "outlier_days")
    assert not outlier_check.passed


# ---------------------------------------------------------------------------
# _aggregate_validity unit tests
# ---------------------------------------------------------------------------


def test_aggregate_all_pass_returns_valid():
    checks = [
        ValidationCheck("a", True, 0.0, "info", "", ""),
        ValidationCheck("b", True, 0.0, "warning", "", ""),
    ]
    validity, can_trust, rec = _aggregate_validity(checks)
    assert validity == "VALID"
    assert can_trust is True


def test_aggregate_critical_failure_returns_invalid():
    checks = [
        ValidationCheck("a", False, 0.0, "critical", "", ""),
        ValidationCheck("b", True, 0.0, "info", "", ""),
    ]
    validity, can_trust, _ = _aggregate_validity(checks)
    assert validity == "INVALID"
    assert can_trust is False


def test_aggregate_warning_failure_returns_warning():
    checks = [
        ValidationCheck("a", False, 0.0, "warning", "", ""),
        ValidationCheck("b", True, 0.0, "info", "", ""),
    ]
    validity, can_trust, _ = _aggregate_validity(checks)
    assert validity == "WARNING"
    assert can_trust is True


def test_aggregate_critical_beats_warning():
    """INVALID must take precedence over WARNING."""
    checks = [
        ValidationCheck("a", False, 0.0, "critical", "", ""),
        ValidationCheck("b", False, 0.0, "warning", "", ""),
    ]
    validity, can_trust, _ = _aggregate_validity(checks)
    assert validity == "INVALID"
    assert can_trust is False


# ---------------------------------------------------------------------------
# detect_outlier_days unit tests
# ---------------------------------------------------------------------------


def test_detect_outlier_clean_data_passes():
    check = detect_outlier_days(_clean_daily())
    assert check.passed


def test_detect_outlier_returns_validation_check():
    check = detect_outlier_days(_clean_daily())
    assert isinstance(check, ValidationCheck)
    assert check.name == "outlier_days"


def test_detect_outlier_score_is_fraction():
    check = detect_outlier_days(_clean_daily())
    assert 0.0 <= check.score <= 1.0


# ---------------------------------------------------------------------------
# check_srm edge cases
# ---------------------------------------------------------------------------


def test_srm_zero_subjects():
    check = check_srm(pd.Series([0, 0, 0]), pd.Series([0, 0, 0]))
    assert not check.passed
    assert check.severity == "critical"


def test_srm_score_is_p_value():
    """Score field must be the p-value (0–1)."""
    n_control = pd.Series([500] * 14)
    n_treatment = pd.Series([500] * 14)
    check = check_srm(n_control, n_treatment)
    assert 0.0 <= check.score <= 1.0


# ---------------------------------------------------------------------------
# baseline_period parameter for volume spike
# ---------------------------------------------------------------------------


def test_volume_spike_with_explicit_baseline():
    df = _clean_daily()
    baseline = df["date"][:5]  # first 5 days as DatetimeIndex
    df_indexed = df.set_index("date")
    check = check_volume_spike(
        df_indexed["n_control"],
        df_indexed["n_treatment"],
        baseline_period=baseline,
    )
    assert isinstance(check, ValidationCheck)

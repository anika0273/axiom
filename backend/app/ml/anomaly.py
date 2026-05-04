"""
Experiment validity guardrails for A/B test data quality.

Detects data contamination that would invalidate experiment results:
sample ratio mismatch, outlier days (bot attacks, pipeline failures),
metric drift via CUSUM, and volume spikes.

Usage::

    validation = validate_experiment(daily_metrics)
    print(validation.overall_validity)   # "VALID" | "WARNING" | "INVALID"
    print(validation.recommendation)
    print(validation.can_trust_results)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

_MIN_DAYS = 7
_BASELINE_FRACTION = 0.20        # use first 20% of days when no baseline given
_VOLUME_SPIKE_SIGMA = 3.0        # flag days > 3σ above baseline mean
_CUSUM_CRITICAL_CROSSINGS = 2    # CUSUM is critical when threshold crossed ≥ twice
_OUTLIER_CRITICAL_FRACTION = 0.20  # outlier / volume checks become critical above 20% days
_SRM_ALPHA = 0.01                # chi-squared significance level for SRM


@dataclass
class ValidationCheck:
    """Result of one validity check.

    Attributes:
        name: Short machine-readable identifier, e.g. "srm_check".
        passed: True when the check found no problem.
        score: Numeric severity proxy (interpretation is check-specific).
        severity: "info" | "warning" | "critical".
        description: Human-readable summary of what was found.
        action: What the analyst should do about it.
    """

    name: str
    passed: bool
    score: float
    severity: Literal["info", "warning", "critical"]
    description: str
    action: str


@dataclass
class ExperimentValidation:
    """Aggregate validity verdict for an experiment.

    Attributes:
        overall_validity: "VALID" | "WARNING" | "INVALID".
        checks: Individual check results, one per detector.
        recommendation: Standard prose recommendation for the analyst.
        can_trust_results: False when any critical check fails.
    """

    overall_validity: Literal["VALID", "WARNING", "INVALID"]
    checks: list[ValidationCheck]
    recommendation: str
    can_trust_results: bool


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_srm(
    n_control: pd.Series,
    n_treatment: pd.Series,
    expected_ratio: float = 0.5,
) -> ValidationCheck:
    """Check for Sample Ratio Mismatch using a chi-squared test.

    A broken randomization mechanism will assign subjects to variants in a
    ratio that deviates significantly from the intended split.  Uses
    scipy.stats.chi2_contingency on the aggregate counts — do not reimplement.

    Args:
        n_control: Daily control group counts.
        n_treatment: Daily treatment group counts.
        expected_ratio: Expected fraction of subjects in the treatment group.
            Default 0.5 (50/50 split).

    Returns:
        ValidationCheck with severity="critical" (SRM always is).
    """
    total_control = int(n_control.sum())
    total_treatment = int(n_treatment.sum())
    total = total_control + total_treatment

    if total == 0:
        return ValidationCheck(
            name="srm_check",
            passed=False,
            score=0.0,
            severity="critical",
            description="No subjects observed; cannot validate assignment ratio.",
            action="Verify that event tracking is working before proceeding.",
        )

    expected_treatment = total * expected_ratio
    expected_control = total * (1.0 - expected_ratio)

    # chi2_contingency expects a 2D observed table; use a 1×2 table for
    # goodness-of-fit against the expected split.
    observed = np.array([[total_treatment, total_control]])
    expected = np.array([[expected_treatment, expected_control]])

    # We use chi2_contingency with the lambda_ parameter to get the
    # Pearson chi-squared statistic directly.  For a 1×2 table with fixed
    # expected values we compute the statistic manually via chi2_contingency
    # on the 2×2 contingency table [observed; expected].
    chi2_stat, p_value, _dof, _ex = chi2_contingency(
        np.array([[total_treatment, total_control],
                  [expected_treatment, expected_control]]),
        correction=False,
    )

    actual_ratio = total_treatment / total if total > 0 else 0.0
    passed = p_value >= _SRM_ALPHA

    if passed:
        description = (
            f"Assignment ratio {actual_ratio:.2%} treatment is consistent with "
            f"expected {expected_ratio:.2%} (p={p_value:.4f})."
        )
        action = "No action required."
    else:
        description = (
            f"SRM detected: observed {actual_ratio:.2%} treatment vs expected "
            f"{expected_ratio:.2%} (chi²={chi2_stat:.2f}, p={p_value:.4f}). "
            "Randomization may be broken."
        )
        action = (
            "Halt experiment analysis. Audit the assignment pipeline for "
            "deterministic bucketing bugs, cache poisoning, or bot traffic."
        )

    logger.info("srm_check: p=%.4f passed=%s", p_value, passed)
    return ValidationCheck(
        name="srm_check",
        passed=passed,
        score=float(p_value),
        severity="critical",
        description=description,
        action=action,
    )


def detect_outlier_days(
    daily_metrics: pd.DataFrame,
) -> ValidationCheck:
    """Detect anomalous days using Isolation Forest.

    Fits IsolationForest on [control_metric, treatment_metric, n_control,
    n_treatment] to find days that look unlike the rest of the experiment
    (bot floods, pipeline outages, metric definition changes).

    Uses raw score_samples() with a Tukey-style fence (Q1 − 3×IQR) rather
    than predict() so that genuinely clean datasets produce zero flagged days.
    IsolationForest.predict() with any fixed contamination fraction forces a
    minimum of one outlier per dataset, causing false positives on clean data.

    The check becomes critical when more than 20% of days are flagged.

    Args:
        daily_metrics: DataFrame with columns control_metric, treatment_metric,
            n_control, n_treatment.

    Returns:
        ValidationCheck with severity="warning" or "critical".
    """
    features = daily_metrics[
        ["control_metric", "treatment_metric", "n_control", "n_treatment"]
    ].values.astype(float)

    clf = IsolationForest(contamination="auto", random_state=42)
    clf.fit(features)
    # score_samples: higher = more normal, lower = more isolated (anomalous).
    # Tukey fence at Q1 − 3×IQR: flags only extreme outliers, not the
    # bottom-contamination% of every dataset.
    scores = clf.score_samples(features)
    q1 = float(np.percentile(scores, 25))
    q3 = float(np.percentile(scores, 75))
    iqr = q3 - q1
    lower_fence = q1 - 3.0 * max(iqr, 1e-10)
    outlier_mask = scores < lower_fence
    n_outliers = int(outlier_mask.sum())
    n_total = len(daily_metrics)
    outlier_fraction = n_outliers / n_total

    is_critical = outlier_fraction > _OUTLIER_CRITICAL_FRACTION
    passed = n_outliers == 0

    if passed:
        description = f"No anomalous days detected across {n_total} days."
        action = "No action required."
        severity: Literal["info", "warning", "critical"] = "info"
    elif is_critical:
        description = (
            f"{n_outliers}/{n_total} days ({outlier_fraction:.0%}) flagged as anomalous. "
            "More than 20% of experiment data is suspect."
        )
        action = (
            "Do not use these results. Identify and remove or quarantine "
            "contaminated days before rerunning analysis."
        )
        severity = "critical"
    else:
        description = (
            f"{n_outliers}/{n_total} days ({outlier_fraction:.0%}) flagged as anomalous."
        )
        action = (
            "Review flagged days for bot traffic, tracking outages, or "
            "holiday effects. Consider excluding them from analysis."
        )
        severity = "warning"

    logger.info(
        "outlier_days: n_outliers=%d/%d fraction=%.3f",
        n_outliers, n_total, outlier_fraction,
    )
    return ValidationCheck(
        name="outlier_days",
        passed=passed,
        score=float(outlier_fraction),
        severity=severity,
        description=description,
        action=action,
    )


def check_cusum_drift(
    control_metric: pd.Series,
    treatment_metric: pd.Series,
    threshold: float = 10.0,
) -> ValidationCheck:
    """Detect gradual metric divergence using CUSUM.

    CUSUM (Cumulative Sum control chart): maintains a running sum of
    deviations from a target level.  When the cumsum exceeds a threshold,
    it signals that the process mean has shifted — here, that the
    control–treatment metric gap is trending rather than stationary.

    Algorithm:
        1. Compute daily gap = treatment_metric − control_metric.
        2. Standardise by the gap's rolling std to make the threshold
           scale-independent.
        3. Run two-sided CUSUM: S_high and S_low track positive and
           negative deviations cumulatively, resetting to 0 at each step.
        4. Count crossings (days when either S exceeds threshold).
        5. ≥ 2 crossings → critical; ≥ 1 crossing → warning; 0 → pass.

    Args:
        control_metric: Daily control group metric values.
        treatment_metric: Daily treatment group metric values.
        threshold: CUSUM threshold in standardised units. Default 10.0.

    Returns:
        ValidationCheck with severity "info", "warning", or "critical".
    """
    gap = treatment_metric.values - control_metric.values
    gap_std = float(np.std(gap, ddof=1))

    if gap_std < 1e-10:
        # Zero-variance gap means perfectly flat divergence — no drift.
        logger.info("cusum_drift: zero-variance gap, no drift possible")
        return ValidationCheck(
            name="cusum_drift",
            passed=True,
            score=0.0,
            severity="info",
            description="Metric gap has zero variance; no drift detected.",
            action="No action required.",
        )

    # Mean-centre before standardising: CUSUM should detect CHANGES in the
    # gap (drift), not the constant treatment effect itself.  Without
    # centering, a stable ATE offset would cause perpetual CUSUM crossings.
    gap_mean = float(np.mean(gap))
    standardised = (gap - gap_mean) / gap_std

    # Two-sided CUSUM: S_high detects upward shifts, S_low detects downward.
    # Each resets to 0 when it goes negative/positive respectively,
    # so it only accumulates persistent deviations.
    s_high = 0.0
    s_low = 0.0
    crossings = 0
    max_cusum = 0.0

    for z in standardised:
        s_high = max(0.0, s_high + z)
        s_low = max(0.0, s_low - z)
        peak = max(s_high, s_low)
        if peak > max_cusum:
            max_cusum = peak
        if s_high > threshold or s_low > threshold:
            crossings += 1
            # Reset after crossing so each crossing is independent.
            s_high = 0.0
            s_low = 0.0

    if crossings >= _CUSUM_CRITICAL_CROSSINGS:
        passed = False
        severity: Literal["info", "warning", "critical"] = "critical"
        description = (
            f"CUSUM drift detected: threshold crossed {crossings} time(s) "
            f"(max cumsum={max_cusum:.2f}, threshold={threshold}). "
            "Metric gap is trending, not stationary."
        )
        action = (
            "Investigate external events (releases, seasonality, data pipeline "
            "changes) that may have altered the metric trajectory mid-experiment."
        )
    elif crossings == 1:
        passed = False
        severity = "warning"
        description = (
            f"CUSUM drift: threshold crossed once "
            f"(max cumsum={max_cusum:.2f}, threshold={threshold})."
        )
        action = "Review experiment timeline for any mid-experiment changes."
    else:
        passed = True
        severity = "info"
        description = (
            f"No metric drift detected (max cumsum={max_cusum:.2f}, "
            f"threshold={threshold})."
        )
        action = "No action required."

    logger.info(
        "cusum_drift: crossings=%d max_cusum=%.2f passed=%s",
        crossings, max_cusum, passed,
    )
    return ValidationCheck(
        name="cusum_drift",
        passed=passed,
        score=float(max_cusum),
        severity=severity,
        description=description,
        action=action,
    )


def check_volume_spike(
    n_control: pd.Series,
    n_treatment: pd.Series,
    baseline_period: pd.DatetimeIndex | None = None,
) -> ValidationCheck:
    """Flag days with abnormally high combined traffic volume.

    Computes the baseline mean and std from a reference period, then flags
    any day where total_n > baseline_mean + 3σ.  A spike on a single day
    is a warning; spikes on >20% of days are critical.

    Args:
        n_control: Daily control group counts (same length as n_treatment).
        n_treatment: Daily treatment group counts.
        baseline_period: Optional DatetimeIndex selecting which rows of
            n_control/n_treatment form the baseline.  When None, the first
            20% of days are used.

    Returns:
        ValidationCheck with severity "info", "warning", or "critical".
    """
    total_n = n_control.values.astype(float) + n_treatment.values.astype(float)
    n_days = len(total_n)

    # Determine baseline rows.
    if baseline_period is not None:
        # baseline_period is a positional integer index into total_n when
        # n_control has no DatetimeIndex (common in tests), or a label index
        # when it does.  We support both.
        if isinstance(n_control.index, pd.DatetimeIndex):
            baseline_mask = n_control.index.isin(baseline_period)
            baseline_values = total_n[baseline_mask]
        else:
            # Treat baseline_period as integer positions.
            baseline_values = total_n[np.array(baseline_period)]
    else:
        n_baseline = max(1, int(n_days * _BASELINE_FRACTION))
        baseline_values = total_n[:n_baseline]

    if len(baseline_values) == 0:
        baseline_values = total_n

    baseline_mean = float(np.mean(baseline_values))
    baseline_std = float(np.std(baseline_values, ddof=1)) if len(baseline_values) > 1 else 0.0

    spike_threshold = baseline_mean + _VOLUME_SPIKE_SIGMA * max(baseline_std, 1.0)
    spike_mask = total_n > spike_threshold
    n_spikes = int(spike_mask.sum())
    spike_fraction = n_spikes / n_days

    is_critical = spike_fraction > _OUTLIER_CRITICAL_FRACTION
    passed = n_spikes == 0

    if passed:
        description = (
            f"No volume spikes detected. Baseline mean={baseline_mean:.0f}, "
            f"threshold={spike_threshold:.0f}."
        )
        action = "No action required."
        severity: Literal["info", "warning", "critical"] = "info"
    elif is_critical:
        description = (
            f"{n_spikes}/{n_days} days ({spike_fraction:.0%}) exceed the volume "
            f"spike threshold ({spike_threshold:.0f}). "
            f"Baseline mean={baseline_mean:.0f} ± {baseline_std:.0f}."
        )
        action = (
            "Critical data quality issue. Investigate bot traffic, "
            "load-test contamination, or event-logging bugs."
        )
        severity = "critical"
    else:
        description = (
            f"{n_spikes} day(s) exceed volume spike threshold ({spike_threshold:.0f}). "
            f"Baseline mean={baseline_mean:.0f} ± {baseline_std:.0f}."
        )
        action = (
            "Review spiked days for bot traffic or tracking anomalies. "
            "Consider excluding them from analysis."
        )
        severity = "warning"

    logger.info(
        "volume_spike: n_spikes=%d/%d fraction=%.3f",
        n_spikes, n_days, spike_fraction,
    )
    return ValidationCheck(
        name="volume_spike",
        passed=passed,
        score=float(spike_fraction),
        severity=severity,
        description=description,
        action=action,
    )


# ---------------------------------------------------------------------------
# Validity aggregation
# ---------------------------------------------------------------------------


def _aggregate_validity(
    checks: list[ValidationCheck],
) -> tuple[Literal["VALID", "WARNING", "INVALID"], bool, str]:
    """Derive overall_validity, can_trust_results, and recommendation from checks.

    Rules:
        - Any critical check that did not pass → INVALID, can_trust=False.
        - Any warning check that did not pass → WARNING, can_trust=True.
        - All pass → VALID, can_trust=True.

    Args:
        checks: All ValidationCheck results.

    Returns:
        (overall_validity, can_trust_results, recommendation)
    """
    has_critical_failure = any(
        (not c.passed and c.severity == "critical") for c in checks
    )
    has_warning_failure = any(
        (not c.passed and c.severity == "warning") for c in checks
    )

    if has_critical_failure:
        return (
            "INVALID",
            False,
            "Do not trust these results. Investigate data pipeline before continuing.",
        )
    if has_warning_failure:
        return (
            "WARNING",
            True,
            "Proceed with caution. Review flagged issues before acting on results.",
        )
    return (
        "VALID",
        True,
        "Results are valid. Proceed with analysis.",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_experiment(
    daily_metrics: pd.DataFrame,
    baseline_period: pd.DatetimeIndex | None = None,
) -> ExperimentValidation:
    """Run all validity checks on an experiment's daily metric data.

    Runs four independent checks — SRM, outlier days, CUSUM drift, and
    volume spikes — each in a try/except so that a failure in one check
    never blocks the others.

    daily_metrics must contain columns:
        date, control_metric, treatment_metric, n_control, n_treatment

    Args:
        daily_metrics: Daily experiment data. Must have at least 7 rows.
        baseline_period: Optional DatetimeIndex of reference days for the
            volume spike baseline.  When None, the first 20% of days are used.

    Returns:
        ExperimentValidation with overall verdict, per-check details,
        a plain-English recommendation, and can_trust_results.

    Raises:
        ValueError: If daily_metrics has fewer than 7 rows.
    """
    if len(daily_metrics) < _MIN_DAYS:
        raise ValueError(
            f"validate_experiment requires at least {_MIN_DAYS} days of data; "
            f"got {len(daily_metrics)}."
        )

    checks: list[ValidationCheck] = []

    # Each check is wrapped independently so a bug in one never silences others.
    _check_fns = [
        ("srm_check", lambda: check_srm(
            daily_metrics["n_control"],
            daily_metrics["n_treatment"],
        )),
        ("outlier_days", lambda: detect_outlier_days(daily_metrics)),
        ("cusum_drift", lambda: check_cusum_drift(
            daily_metrics["control_metric"],
            daily_metrics["treatment_metric"],
        )),
        ("volume_spike", lambda: check_volume_spike(
            daily_metrics["n_control"],
            daily_metrics["n_treatment"],
            baseline_period=baseline_period,
        )),
    ]

    for check_name, fn in _check_fns:
        try:
            result = fn()
            logger.info("check %s: passed=%s score=%.4f", check_name, result.passed, result.score)
        except Exception as exc:  # noqa: BLE001
            logger.error("check %s raised unexpectedly: %s", check_name, exc, exc_info=True)
            result = ValidationCheck(
                name=check_name,
                passed=False,
                score=0.0,
                severity="warning",
                description=f"Check could not complete: {exc}",
                action="Investigate the error before trusting this check's result.",
            )
        checks.append(result)

    overall_validity, can_trust, recommendation = _aggregate_validity(checks)

    return ExperimentValidation(
        overall_validity=overall_validity,
        checks=checks,
        recommendation=recommendation,
        can_trust_results=can_trust,
    )

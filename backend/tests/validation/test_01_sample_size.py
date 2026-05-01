"""Validation 1 — Sample size against the two-sample Wald closed-form.

External reference
------------------
The correct Wald formula for a TWO-SAMPLE z-test with equal groups is:

    n_per_group = 2 * ((z_α/2 + z_β) / d)²

where d = |mde| / sqrt(p_bar * (1 - p_bar)) is Cohen's d for proportions and
p_bar = baseline + mde/2.

The implementation uses statsmodels NormalIndPower().solve_power(), which
numerically inverts the same power function.  Expected agreement: < 1 %.

Tolerance
---------
5 % relative: both approaches are correct approximations to the same
underlying power integral; the closed-form rounds differently at small d.

Failure diagnosis
-----------------
If delta > 5 %:
  • absolute vs relative MDE: check whether caller passed mde as a fraction
    of the baseline (relative) instead of an absolute rate difference.
  • one-sided vs two-sided mismatch: one-sided needs z_α not z_α/2.
  • formula bug: verify the factor-of-2 in n = 2*(...)².
"""
from __future__ import annotations

import math

import pytest
from scipy.stats import norm

from app.stats.power import calculate_sample_size
from tests.validation._report import record

# ---------------------------------------------------------------------------
# Wald reference helper (correct two-sample formula)
# ---------------------------------------------------------------------------


def _wald_n(
    baseline: float,
    mde: float,
    alpha: float,
    power: float,
    two_tailed: bool,
) -> int:
    """Two-sample Wald formula: n_per_group = 2 * ((z_a + z_b) / d)²."""
    p_bar = baseline + mde / 2.0
    pooled_sd = math.sqrt(p_bar * (1.0 - p_bar))
    d = abs(mde) / pooled_sd
    z_a = norm.ppf(1.0 - alpha / 2.0) if two_tailed else norm.ppf(1.0 - alpha)
    z_b = norm.ppf(power)
    return math.ceil(2.0 * ((z_a + z_b) / d) ** 2)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

_TOLERANCE_PCT = 5.0
_MODULE = "sample_size"


def _run_scenario(
    label: str,
    baseline: float,
    mde: float,
    alpha: float,
    power: float,
    two_tailed: bool,
    notes: str = "",
) -> None:
    ref_n = _wald_n(baseline, mde, alpha, power, two_tailed)
    result = calculate_sample_size(baseline, mde, alpha, power, two_tailed)
    obs_n = result.control_size

    delta_pct = abs(obs_n - ref_n) / ref_n * 100.0
    passed = delta_pct <= _TOLERANCE_PCT

    likely_cause = ""
    if not passed:
        if delta_pct > 90.0:
            likely_cause = "Factor-of-2 error: formula may give n/2 instead of n."
        elif delta_pct > 30.0:
            likely_cause = (
                "Large deviation — check absolute vs relative MDE interpretation, "
                "or one-sided vs two-sided mismatch."
            )
        else:
            likely_cause = (
                f"Moderate deviation ({delta_pct:.1f}%) — likely rounding policy "
                "or numerical solver vs closed-form divergence."
            )

    record(
        module=_MODULE,
        scenario=label,
        expected=f"{ref_n:,}",
        observed=f"{obs_n:,}",
        delta=f"{delta_pct:.2f}%",
        tolerance=f"≤{_TOLERANCE_PCT}%",
        passed=passed,
        likely_cause=likely_cause,
        notes=notes,
    )

    assert passed, (
        f"{label}: Wald reference = {ref_n:,}, implementation = {obs_n:,} "
        f"({delta_pct:.1f}% off, tolerance {_TOLERANCE_PCT}%). "
        f"Likely cause: {likely_cause}"
    )


def test_s1_canonical_absolute_mde() -> None:
    """Canonical: baseline=5%, MDE=+1pp absolute, α=0.05, 80% power, two-tailed.

    Published reference (statsmodels NormalIndPower): ≈ 8,159 per group.
    Wald formula: n = 2 * ((z_0.025 + z_0.20) / d)² ≈ 8,161 per group.
    Agreement within 0.025% is expected.
    """
    _run_scenario(
        label="S1: baseline=5%, MDE=+1pp, α=0.05, 80% power, two-tailed",
        baseline=0.05,
        mde=0.01,
        alpha=0.05,
        power=0.80,
        two_tailed=True,
        notes="Canonical e-commerce conversion-rate scenario.",
    )


def test_s2_high_baseline() -> None:
    """Higher baseline: 30% rate, +3pp MDE, α=0.05, 80% power, two-tailed.

    At higher rates the Bernoulli variance is larger, requiring fewer samples
    than low-rate metrics to achieve the same absolute effect.
    """
    _run_scenario(
        label="S2: baseline=30%, MDE=+3pp, α=0.05, 80% power, two-tailed",
        baseline=0.30,
        mde=0.03,
        alpha=0.05,
        power=0.80,
        two_tailed=True,
    )


def test_s3_high_power() -> None:
    """90% power: baseline=10%, MDE=+2pp, α=0.05, two-tailed.

    Higher power (90% vs 80%) requires a larger z_β and therefore a larger n.
    The sample size should be roughly 35% larger than the 80%-power equivalent.
    """
    _run_scenario(
        label="S3: baseline=10%, MDE=+2pp, α=0.05, 90% power, two-tailed",
        baseline=0.10,
        mde=0.02,
        alpha=0.05,
        power=0.90,
        two_tailed=True,
    )


def test_s4_one_sided() -> None:
    """One-sided: baseline=10%, MDE=+2pp, α=0.05, 80% power.

    One-sided tests use z_α instead of z_α/2, reducing the required n relative
    to the two-sided equivalent.  Implementation achieves this by doubling alpha
    before passing to NormalIndPower.
    """
    result_two = calculate_sample_size(0.10, 0.02, 0.05, 0.80, two_tailed=True)
    _run_scenario(
        label="S4: baseline=10%, MDE=+2pp, α=0.05, 80% power, one-sided",
        baseline=0.10,
        mde=0.02,
        alpha=0.05,
        power=0.80,
        two_tailed=False,
        notes=(
            f"One-sided n must be < two-sided n ({result_two.control_size:,}). "
            "Ratio should be ≈ 0.75."
        ),
    )
    # Additional structural check: one-sided requires fewer samples.
    result_one = calculate_sample_size(0.10, 0.02, 0.05, 0.80, two_tailed=False)
    assert result_one.control_size < result_two.control_size, (
        f"One-sided n ({result_one.control_size:,}) must be < "
        f"two-sided n ({result_two.control_size:,})."
    )


def test_s5_strict_alpha() -> None:
    """Strict alpha: baseline=5%, MDE=+1pp, α=0.01, 80% power, two-tailed.

    Tightening alpha from 0.05 to 0.01 substantially increases n because the
    critical z rises from 1.96 to 2.576.
    """
    ref_loose = _wald_n(0.05, 0.01, 0.05, 0.80, True)
    _run_scenario(
        label="S5: baseline=5%, MDE=+1pp, α=0.01, 80% power, two-tailed",
        baseline=0.05,
        mde=0.01,
        alpha=0.01,
        power=0.80,
        two_tailed=True,
        notes=f"Should require more samples than α=0.05 equivalent ({ref_loose:,}).",
    )
    result = calculate_sample_size(0.05, 0.01, 0.01, 0.80)
    assert result.control_size > ref_loose, (
        "α=0.01 must require more samples than α=0.05."
    )

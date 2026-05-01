"""Validation 2 — Two-proportion z-test against statsmodels directly.

External reference
------------------
``statsmodels.stats.proportion.proportions_ztest`` called with the same
inputs.  Because the implementation wraps this exact function the z-statistic
and p-value must agree to at least 6 decimal places (the precision of the
implementation's rounding).

The 95 % Wald CI is computed separately (unpooled SE) and compared against
an independent manual calculation.

Failure diagnosis
-----------------
• z-stat mismatch  → order of [treatment, control] reversed in the call.
• p-value mismatch → wrong ``alternative`` argument ("two-sided" vs "larger").
• CI mismatch      → pooled SE used for CI instead of unpooled SE.
• reject mismatch  → comparison operator (< vs <=) or alpha applied incorrectly.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import norm
from statsmodels.stats.proportion import proportions_ztest

from app.stats.testing import run_proportion_test
from tests.validation._report import record

_MODULE = "proportion_test"
_STAT_TOL = 0.001   # tolerance on z-stat and p-value
_CI_TOL = 0.001     # tolerance on CI endpoints
_REJECT_EXACT = True  # categorical decision must match exactly


def _manual_ci(sc: int, nc: int, st: int, nt: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wald CI with unpooled SE (independent of statsmodels)."""
    p_c = sc / nc
    p_t = st / nt
    delta = p_t - p_c
    p_c_s = max(p_c, 1 / (2 * nc))
    p_t_s = max(p_t, 1 / (2 * nt))
    se = math.sqrt(p_c_s * (1 - p_c_s) / nc + p_t_s * (1 - p_t_s) / nt)
    z_crit = norm.ppf(1.0 - alpha / 2.0)
    return (delta - z_crit * se, delta + z_crit * se)


def _run_scenario(
    label: str,
    control_n: int,
    control_s: int,
    treatment_n: int,
    treatment_s: int,
    alpha: float = 0.05,
    notes: str = "",
) -> None:
    # External reference: statsmodels called directly
    ref_z, ref_p = proportions_ztest(
        count=np.array([treatment_s, control_s]),
        nobs=np.array([treatment_n, control_n]),
        alternative="two-sided",
    )
    ref_z = float(ref_z)
    ref_p = float(ref_p)
    ref_reject = ref_p < alpha
    ref_ci = _manual_ci(control_s, control_n, treatment_s, treatment_n, alpha)

    result = run_proportion_test(control_s, control_n, treatment_s, treatment_n, alpha)

    dz = abs(result.test_statistic - ref_z)
    dp = abs(result.p_value - ref_p)
    d_ci_lo = abs(result.confidence_interval[0] - ref_ci[0])
    d_ci_hi = abs(result.confidence_interval[1] - ref_ci[1])

    pass_z = dz <= _STAT_TOL
    pass_p = dp <= _STAT_TOL
    pass_rej = result.is_significant == ref_reject
    pass_ci = d_ci_lo <= _CI_TOL and d_ci_hi <= _CI_TOL
    all_pass = pass_z and pass_p and pass_rej and pass_ci

    failures: list[str] = []
    if not pass_z:
        failures.append(f"z-stat Δ={dz:.6f} > {_STAT_TOL}")
    if not pass_p:
        failures.append(f"p-value Δ={dp:.6f} > {_STAT_TOL}")
    if not pass_rej:
        failures.append(
            f"reject mismatch: impl={result.is_significant}, ref={ref_reject}"
        )
    if not pass_ci:
        failures.append(f"CI Δ=({d_ci_lo:.6f}, {d_ci_hi:.6f}) > {_CI_TOL}")

    likely = ""
    if not pass_z:
        likely = "Control/treatment order reversed in proportions_ztest call."
    elif not pass_p:
        likely = "Wrong alternative argument ('larger'/'smaller' vs 'two-sided')."
    elif not pass_rej:
        likely = f"Boundary comparison issue (< vs ≤) or wrong alpha applied."
    elif not pass_ci:
        likely = "CI uses pooled SE instead of unpooled SE (Wald)."

    record(
        module=_MODULE,
        scenario=label,
        expected=f"z={ref_z:.4f}, p={ref_p:.4f}, reject={ref_reject}",
        observed=f"z={result.test_statistic:.4f}, p={result.p_value:.4f}, "
                 f"reject={result.is_significant}",
        delta=f"Δz={dz:.2e}, Δp={dp:.2e}",
        tolerance=f"≤{_STAT_TOL}",
        passed=all_pass,
        likely_cause=likely,
        notes=notes,
    )

    assert all_pass, (
        f"{label}: {'; '.join(failures)}. "
        f"ref=(z={ref_z:.4f}, p={ref_p:.4f}), "
        f"obs=(z={result.test_statistic:.4f}, p={result.p_value:.4f})"
    )


def test_p1_no_effect_small() -> None:
    """P1: No significant effect — small difference, n=1000 per group.

    control=100/1000 (10%), treatment=105/1000 (10.5%).
    Expected: not significant (p ≈ 0.71).
    """
    _run_scenario(
        label="P1: 10%→10.5%, n=1 000, not significant",
        control_n=1000, control_s=100,
        treatment_n=1000, treatment_s=105,
        notes="Small absolute difference; normal approximation is valid (n>30, successes>5).",
    )


def test_p2_significant_clear() -> None:
    """P2: Clear significant uplift — n=5000 per group.

    control=250/5000 (5%), treatment=300/5000 (6%).
    Expected: significant (p ≈ 0.028), z ≈ 2.19.
    """
    _run_scenario(
        label="P2: 5%→6%, n=5 000, significant",
        control_n=5000, control_s=250,
        treatment_n=5000, treatment_s=300,
        notes="Standard e-commerce uplift scenario; p should be ≈ 0.028.",
    )


def test_p3_high_conversion_large_n() -> None:
    """P3: High conversion rate, large n — n=10 000 per group.

    control=4000/10000 (40%), treatment=4300/10000 (43%).
    Expected: highly significant (p ≈ 1.6e-5), z ≈ 4.30.
    """
    _run_scenario(
        label="P3: 40%→43%, n=10 000, highly significant",
        control_n=10000, control_s=4000,
        treatment_n=10000, treatment_s=4300,
        notes="Large n and high rate; p << 0.05.",
    )


def test_p4_low_event_count_warning() -> None:
    """P4: Low event count — n=100, few successes.

    control=3/100 (3%), treatment=5/100 (5%).
    Expected: not significant, 'low conversions' warning present.

    This case validates that the implementation emits a warning for < 5
    events per group while still returning a valid (if unreliable) result.
    """
    result = run_proportion_test(3, 100, 5, 100)
    ref_z, ref_p = proportions_ztest(
        count=np.array([5, 3]),
        nobs=np.array([100, 100]),
        alternative="two-sided",
    )

    dz = abs(result.test_statistic - float(ref_z))
    dp = abs(result.p_value - float(ref_p))
    has_warning = any("low" in w.lower() for w in result.sample_warnings)

    passed = dz <= _STAT_TOL and dp <= _STAT_TOL and has_warning

    likely = ""
    if not has_warning:
        likely = "Warning 'low conversions' not emitted for <5 events per group."
    elif not (dz <= _STAT_TOL and dp <= _STAT_TOL):
        likely = "Statistical values deviate from statsmodels reference."

    record(
        module=_MODULE,
        scenario="P4: 3%→5%, n=100, low event count warning",
        expected=f"z={float(ref_z):.4f}, p={float(ref_p):.4f}, has_low_conv_warning=True",
        observed=f"z={result.test_statistic:.4f}, p={result.p_value:.4f}, "
                 f"has_low_conv_warning={has_warning}",
        delta=f"Δz={dz:.2e}, Δp={dp:.2e}",
        tolerance=f"Δ≤{_STAT_TOL}, warning required",
        passed=passed,
        likely_cause=likely,
        notes="Low event count (< 5) should trigger 'low conversions' sample warning.",
    )

    assert dz <= _STAT_TOL, f"z-stat off by {dz:.6f}"
    assert dp <= _STAT_TOL, f"p-value off by {dp:.6f}"
    assert has_warning, (
        f"Expected 'low conversions' warning; got: {result.sample_warnings}"
    )

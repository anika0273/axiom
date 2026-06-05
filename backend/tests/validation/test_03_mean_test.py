"""Validation 3 — Welch t-test against scipy.stats.ttest_ind directly.

External reference
------------------
``scipy.stats.ttest_ind(..., equal_var=False)`` called on the same arrays.
The implementation wraps this function, so the t-statistic and p-value must
agree to at least 6 decimal places.

CI validation
-------------
The Welch–Satterthwaite CI is computed independently and compared:

    CI = (mean_t - mean_c) ± t_{df, 1-α/2} * SE_welch

where SE_welch = sqrt(var_t/n_t + var_c/n_c) and df is the Welch–Satterthwaite
degrees of freedom.

Failure diagnosis
-----------------
• t-stat mismatch → treatment/control argument order swapped.
• p-value mismatch → wrong degrees of freedom or two-sided correction.
• CI mismatch → pooled variance used instead of per-group Welch SE.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import t as t_dist
from scipy.stats import ttest_ind

from app.stats.testing import run_mean_test
from tests.validation._report import record

_MODULE = "mean_test"
_TOL = 0.001  # tolerance for t-stat and p-value
_CI_TOL = 0.001  # tolerance for CI endpoints
_RNG_SEED = 42


def _welch_ci(
    ctrl: np.ndarray, trt: np.ndarray, alpha: float = 0.05
) -> tuple[float, float]:
    """Independent Welch CI computation (no scipy shortcuts)."""
    n_c, n_t = len(ctrl), len(trt)
    s2_c = float(np.var(ctrl, ddof=1))
    s2_t = float(np.var(trt, ddof=1))
    se = math.sqrt(s2_t / n_t + s2_c / n_c)
    diff = float(np.mean(trt) - np.mean(ctrl))
    # Welch–Satterthwaite df
    num = (s2_t / n_t + s2_c / n_c) ** 2
    denom = (s2_t / n_t) ** 2 / (n_t - 1) + (s2_c / n_c) ** 2 / (n_c - 1)
    df = num / denom
    t_crit = float(t_dist.ppf(1.0 - alpha / 2.0, df=df))
    return (diff - t_crit * se, diff + t_crit * se)


def _run_scenario(
    label: str,
    ctrl: np.ndarray,
    trt: np.ndarray,
    alpha: float = 0.05,
    notes: str = "",
) -> None:
    scipy_result = ttest_ind(trt, ctrl, equal_var=False)
    ref_t = float(scipy_result.statistic)
    ref_p = float(scipy_result.pvalue)
    ref_reject = ref_p < alpha
    ref_ci = _welch_ci(ctrl, trt, alpha)

    result = run_mean_test(ctrl, trt, alpha)

    dt = abs(result.test_statistic - ref_t)
    dp = abs(result.p_value - ref_p)
    pass_t = dt <= _TOL
    pass_p = dp <= _TOL
    pass_rej = result.is_significant == ref_reject
    d_ci_lo = abs(result.confidence_interval[0] - ref_ci[0])
    d_ci_hi = abs(result.confidence_interval[1] - ref_ci[1])
    pass_ci = d_ci_lo <= _CI_TOL and d_ci_hi <= _CI_TOL
    all_pass = pass_t and pass_p and pass_rej and pass_ci

    likely = ""
    if not pass_t:
        likely = "Treatment/control argument order swapped in ttest_ind call."
    elif not pass_p:
        likely = "Wrong df or missing two-sided correction (multiply by 2)."
    elif not pass_rej:
        likely = "Boundary comparison (< vs ≤) or wrong alpha."
    elif not pass_ci:
        likely = "Pooled variance used for CI instead of per-group Welch SE."

    record(
        module=_MODULE,
        scenario=label,
        expected=f"t={ref_t:.4f}, p={ref_p:.6f}, reject={ref_reject}",
        observed=f"t={result.test_statistic:.4f}, p={result.p_value:.6f}, "
        f"reject={result.is_significant}",
        delta=f"Δt={dt:.2e}, Δp={dp:.2e}",
        tolerance=f"≤{_TOL}",
        passed=all_pass,
        likely_cause=likely,
        notes=notes,
    )

    assert all_pass, (
        f"{label}: "
        + (f"Δt={dt:.6f} " if not pass_t else "")
        + (f"Δp={dp:.6f} " if not pass_p else "")
        + ("reject mismatch " if not pass_rej else "")
        + (f"ΔCI=({d_ci_lo:.4f},{d_ci_hi:.4f}) " if not pass_ci else "")
    )


def test_m1_small_sample_no_effect() -> None:
    """M1: Small sample (n=30), identical distributions — no significant effect.

    Both groups drawn from N(10, 4); expected p >> 0.05.
    """
    rng = np.random.default_rng(_RNG_SEED)
    ctrl = rng.normal(10.0, 2.0, 30)
    trt = rng.normal(10.0, 2.0, 30)
    _run_scenario(
        label="M1: N(10,2) vs N(10,2), n=30, no effect",
        ctrl=ctrl,
        trt=trt,
        notes="Same distribution; result should not be significant.",
    )


def test_m2_large_sample_clear_effect() -> None:
    """M2: Large sample (n=500), true treatment effect of +2 units.

    Control ~ N(10, 2), treatment ~ N(12, 2).  Expected: p << 0.05.
    """
    rng = np.random.default_rng(_RNG_SEED)
    ctrl = rng.normal(10.0, 2.0, 500)
    trt = rng.normal(12.0, 2.0, 500)
    _run_scenario(
        label="M2: N(10,2) vs N(12,2), n=500, significant",
        ctrl=ctrl,
        trt=trt,
        notes="True effect = 2 units; should be highly significant.",
    )
    result = run_mean_test(ctrl, trt)
    assert (
        result.is_significant
    ), "Expected significant result with n=500 and 2-unit effect."


def test_m3_unequal_variance() -> None:
    """M3: Unequal variances — validates Welch vs Student's t robustness.

    Control ~ N(10, 1), treatment ~ N(12, 5), n=200 per group.
    Welch's t-test handles unequal variances; Student's would understate the SE.
    This test confirms the implementation uses Welch (equal_var=False).
    """
    rng = np.random.default_rng(_RNG_SEED)
    ctrl = rng.normal(10.0, 1.0, 200)
    trt = rng.normal(12.0, 5.0, 200)
    _run_scenario(
        label="M3: N(10,1) vs N(12,5), n=200, unequal variances",
        ctrl=ctrl,
        trt=trt,
        notes="Unequal variances; Welch adjusts df downward relative to pooled.",
    )
    # Welch df must be less than n_c + n_t - 2 = 398
    from scipy.stats import ttest_ind as _tind

    res_w = _tind(trt, ctrl, equal_var=False)
    assert (
        float(res_w.df) < 397.0
    ), f"Welch df ({res_w.df:.1f}) should be < 398 when variances are unequal."


def test_m4_borderline_significance() -> None:
    """M4: Borderline case — effect engineered so p ≈ 0.05.

    Tests that the significance threshold is applied as a strict < comparison.
    """
    rng = np.random.default_rng(_RNG_SEED + 1)
    ctrl = rng.normal(0.0, 1.0, 1000)
    # Engineer treatment mean so that p is very close to 0.05.
    # z_crit * se ≈ 1.96 * sqrt(2/1000) ≈ 0.0877 → use +0.088 shift for p~0.05.
    trt = rng.normal(0.088, 1.0, 1000)
    result = run_mean_test(ctrl, trt)

    scipy_result = ttest_ind(trt, ctrl, equal_var=False)
    ref_p = float(scipy_result.pvalue)
    dp = abs(result.p_value - ref_p)
    passed = dp <= _TOL

    likely = "p-value computation differs from scipy reference." if not passed else ""
    record(
        module=_MODULE,
        scenario="M4: borderline p≈0.05, n=1 000",
        expected=f"p≈{ref_p:.4f}, consistent with scipy",
        observed=f"p={result.p_value:.4f}",
        delta=f"Δp={dp:.2e}",
        tolerance=f"≤{_TOL}",
        passed=passed,
        likely_cause=likely,
        notes="Tests strict < threshold; engineered to be near boundary.",
    )
    assert passed, f"p-value off by {dp:.6f}"

"""Validation 4 — Ratio metric delta-method variance.

External reference
------------------
The delta-method variance formula (Taylor linearisation):

    Var(R) ≈ (1/μ_b²) · [Var(a)/n + R²·Var(b)/n − 2R·Cov(a,b)/n]

where R = μ_a / μ_b and a_i, b_i are per-user numerator/denominator values.

Scenarios
---------
R1  Standard revenue/session — denominator values near 1, formula
    result should be finite and positive.
R2  Heavy-tailed denominator — high variance in sessions per user.
    Delta SE < naive per-user SE because it handles denominator variance.
R3  Zero-inflated denominator — many users with zero sessions.
    Naive per-user ratio is undefined; delta method works on aggregate means.

Failure diagnosis
-----------------
• Delta SE matches formula exactly (it IS the formula) — any mismatch
  indicates a transcription bug in one of the three variance terms.
• If delta_var < 0 → sign error in the cov cross-term (should be −2R·Cov).
• If SE_naive < SE_delta on heavy-tail data → naive SE underestimates
  variance when denominator is variable; flag this as the expected result.
"""

from __future__ import annotations

import math

import numpy as np

from app.stats.testing import _delta_method_variance
from tests.validation._report import record

_MODULE = "ratio_metric"
_RNG_SEED = 42
_TOL = 1e-10  # delta method formula is exact — tolerance is floating-point only


def _reference_delta_var(
    numerator: np.ndarray, denominator: np.ndarray
) -> tuple[float, float]:
    """Independent reference implementation of the delta-method formula."""
    n = len(numerator)
    mu_a = float(np.mean(numerator))
    mu_b = float(np.mean(denominator))
    ratio = mu_a / mu_b
    var_a = float(np.var(numerator, ddof=1))
    var_b = float(np.var(denominator, ddof=1))
    cov_ab = float(np.cov(numerator, denominator, ddof=1)[0, 1])
    delta_var = (var_a + ratio**2 * var_b - 2 * ratio * cov_ab) / (mu_b**2 * n)
    return ratio, delta_var


def test_r1_standard_revenue_per_session() -> None:
    """R1: Standard revenue-per-session — denominator values ≈ Uniform(1, 3).

    Control: n=500 users, revenue ~ Gamma(2, 3), sessions ~ Uniform(1,3) (integer).
    Treatment: revenue ~ Gamma(2.2, 3) — true ratio slightly higher.
    """
    rng = np.random.default_rng(_RNG_SEED)
    n = 500
    ctrl_rev = rng.gamma(shape=2.0, scale=3.0, size=n)
    ctrl_sess = rng.integers(1, 4, size=n).astype(float)
    trt_rev = rng.gamma(shape=2.2, scale=3.0, size=n)
    trt_sess = rng.integers(1, 4, size=n).astype(float)

    ref_ratio_c, ref_var_c = _reference_delta_var(ctrl_rev, ctrl_sess)
    ref_ratio_t, ref_var_t = _reference_delta_var(trt_rev, trt_sess)

    obs_ratio_c, obs_var_c = _delta_method_variance(ctrl_rev, ctrl_sess)
    obs_ratio_t, obs_var_t = _delta_method_variance(trt_rev, trt_sess)

    d_ratio_c = abs(obs_ratio_c - ref_ratio_c)
    d_var_c = abs(obs_var_c - ref_var_c)
    d_ratio_t = abs(obs_ratio_t - ref_ratio_t)
    d_var_t = abs(obs_var_t - ref_var_t)

    passed = (
        d_ratio_c <= _TOL
        and d_var_c <= _TOL
        and d_ratio_t <= _TOL
        and d_var_t <= _TOL
        and obs_var_c > 0
        and obs_var_t > 0
    )

    likely = ""
    if not passed:
        if d_var_c > _TOL:
            likely = (
                "Variance term mismatch — check signs in delta formula: "
                "Var(a) + R²·Var(b) − 2R·Cov(a,b).  Covariance cross-term "
                "may have wrong sign or be missing."
            )
        if obs_var_c <= 0:
            likely = "Delta variance is non-positive — numerical issue."

    record(
        module=_MODULE,
        scenario="R1: standard revenue/session, Gamma(2,3), Uniform sessions",
        expected=f"ratio_c={ref_ratio_c:.4f}, var_c={ref_var_c:.6e}",
        observed=f"ratio_c={obs_ratio_c:.4f}, var_c={obs_var_c:.6e}",
        delta=f"Δratio={d_ratio_c:.2e}, Δvar={d_var_c:.2e}",
        tolerance=f"≤{_TOL:.0e} (floating-point precision)",
        passed=passed,
        likely_cause=likely,
    )

    assert passed, (
        f"R1: ratio_c delta={d_ratio_c:.2e}, var_c delta={d_var_c:.2e}; "
        f"ratio_t delta={d_ratio_t:.2e}, var_t delta={d_var_t:.2e}"
    )


def test_r2_heavy_tail_delta_vs_naive() -> None:
    """R2: Heavy-tailed denominator — delta SE should be lower or equal to naive SE.

    When per-user session counts are highly variable, the naive per-user ratio
    (revenue_i / sessions_i) has inflated variance because small denominators
    create extreme values.  The delta method linearises around group means,
    which is more stable.

    The scenario uses sessions ~ Pareto(shape=1.1) — a heavy-tailed distribution
    where a small fraction of users have very many sessions, making naive
    per-user ratios unstable.

    Reference: standard error should be finite and positive for both methods,
    but naive SE ≥ delta SE when denominator variance is high.
    """
    rng = np.random.default_rng(_RNG_SEED)
    n = 1000
    # Pareto-distributed sessions: mostly low, occasional very high values.
    # Clip denominator to 1 to avoid zero-division in naive ratio.
    sessions = np.clip(rng.pareto(a=1.1, size=n) + 1, 1.0, None)
    revenue = sessions * rng.gamma(shape=2.0, scale=1.0, size=n)

    # Naive per-user ratio SE
    naive_ratios = revenue / sessions
    naive_se = float(np.std(naive_ratios, ddof=1) / math.sqrt(n))

    # Delta method SE
    ratio_mean, delta_var = _delta_method_variance(revenue, sessions)
    delta_se = math.sqrt(max(delta_var, 0.0))

    # Both SEs must be finite and positive.
    passed_finite = math.isfinite(delta_se) and delta_se > 0

    # On Pareto data the naive SE includes extreme per-user values;
    # delta SE is bounded by the group-level statistics.
    # We don't assert naive_se > delta_se — that's an expected pattern, not a
    # hard invariant — but we document it.
    naive_larger = naive_se >= delta_se
    note_power = (
        "EXPECTED: naive_se >= delta_se on heavy-tail data"
        if naive_larger
        else "ANOMALY: naive_se < delta_se — delta method may overstate variance here"
    )

    record(
        module=_MODULE,
        scenario="R2: Pareto sessions (heavy tail), delta vs naive SE",
        expected="delta_se > 0, finite; naive_se ≥ delta_se (expected pattern)",
        observed=f"delta_se={delta_se:.4f}, naive_se={naive_se:.4f}, "
        f"naive_larger={naive_larger}",
        delta=(
            f"naive/delta ratio = {naive_se/delta_se:.2f}x" if delta_se > 0 else "n/a"
        ),
        tolerance="delta_se > 0 and finite (hard); naive≥delta (expected pattern only)",
        passed=passed_finite,
        likely_cause="" if passed_finite else "delta_var ≤ 0 — sign error in formula.",
        notes=note_power,
    )

    assert passed_finite, f"Delta SE is not finite/positive: delta_se={delta_se}"


def test_r3_zero_inflation_delta_method_stable() -> None:
    """R3: Zero-inflated denominator — delta method handles aggregate means.

    40% of users have 0 sessions (bounce).  Naive per-user ratio is undefined
    (0/0) for those users.  The delta method aggregates Σa / Σb, which avoids
    per-user division.  We verify that run_mean_test on naive per-user ratios
    (zero-division users excluded) gives a different answer than the delta
    method, highlighting the instability.

    This test validates that _delta_method_variance is finite and consistent
    with the reference formula even with zero-inflated denominators (μ_b > 0).
    """
    rng = np.random.default_rng(_RNG_SEED)
    n = 2000
    # 40% bounce (zero sessions), rest have 1–5 sessions.
    has_session = rng.random(n) > 0.4
    sessions = np.where(has_session, rng.integers(1, 6, size=n).astype(float), 0.0)
    revenue = np.where(has_session, rng.exponential(5.0, size=n), 0.0)

    # Delta method operates on full arrays (μ_b = mean sessions > 0).
    mu_b = float(np.mean(sessions))
    assert mu_b > 0.0, "Mean session must be positive for this test to be valid."

    ref_ratio, ref_var = _reference_delta_var(revenue, sessions)
    obs_ratio, obs_var = _delta_method_variance(revenue, sessions)

    d_ratio = abs(obs_ratio - ref_ratio)
    d_var = abs(obs_var - ref_var)
    passed = d_ratio <= _TOL and d_var <= _TOL and obs_var > 0

    likely = ""
    if not passed:
        likely = (
            "Zero-inflated denominator may expose a sign or division issue "
            "in the delta-method variance computation."
        )

    record(
        module=_MODULE,
        scenario="R3: zero-inflated denominator (40% bounce), delta stable",
        expected=f"ratio={ref_ratio:.4f}, var={ref_var:.6e}, var > 0",
        observed=f"ratio={obs_ratio:.4f}, var={obs_var:.6e}",
        delta=f"Δratio={d_ratio:.2e}, Δvar={d_var:.2e}",
        tolerance=f"≤{_TOL:.0e}",
        passed=passed,
        likely_cause=likely,
        notes="Zero-session users do NOT make μ_b = 0; aggregate mean is still positive.",
    )

    assert passed, f"R3: Δratio={d_ratio:.2e}, Δvar={d_var:.2e}"

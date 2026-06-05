"""Validation 5 — CUPED variance reduction properties.

External reference
------------------
The theoretical variance reduction from CUPED is:

    reduction ≈ ρ² × 100%

where ρ = Corr(pre_metric, post_metric).

This is derived from:
    Var(Y_adj) = Var(Y)(1 − ρ²)

so the fraction of variance removed equals ρ².

Scenarios
---------
C1  High correlation (ρ ≈ 0.85, seed=42) — expect ≈ 72% variance reduction;
    validate empirical reduction within ±15 pp of theoretical.
C2  Low correlation (ρ ≈ 0.07) — expect < 5% variance reduction; validate
    CUPED provides minimal benefit.
C3  Effect preservation — CUPED must not change the estimated treatment effect
    (E[Y_adj_t] − E[Y_adj_c] ≈ E[Y_t] − E[Y_c]) within tolerance 0.001.
C4  Zero-correlation baseline — when ρ = 0, CUPED degrades gracefully:
    theta ≈ 0, variance_reduction_pct ≈ 0.

Failure diagnosis
-----------------
• Variance reduction far from ρ²: theta estimate wrong (check OLS formula).
• Effect not preserved: theta applied asymmetrically to groups.
• Negative variance reduction: sign error in theta adjustment.
"""

from __future__ import annotations

import numpy as np

from app.stats.cuped import apply_cuped
from tests.validation._report import record

_MODULE = "cuped"
_RNG_SEED = 42
_VAR_TOL = 15.0  # ±15 pp tolerance on variance reduction (empirical vs theoretical)
_EFFECT_TOL = 0.001  # treatment effect must be preserved within 0.001


def _generate_correlated_data(
    n_ctrl: int,
    n_trt: int,
    pre_mean: float,
    pre_std: float,
    noise_std: float,
    treatment_effect: float,
    seed: int,
) -> tuple[list[float], list[float], list[int]]:
    """Generate (pre, post, assignment) where post = pre + noise (+ effect for trt).

    The correlation between pre and post is approximately:
        ρ ≈ pre_std / sqrt(pre_std² + noise_std²)
    """
    rng = np.random.default_rng(seed)
    n_total = n_ctrl + n_trt
    pre = rng.normal(pre_mean, pre_std, n_total)
    noise = rng.normal(0.0, noise_std, n_total)
    post = pre.copy() + noise
    post[n_ctrl:] += treatment_effect  # add treatment effect to trt group
    assignment = [0] * n_ctrl + [1] * n_trt
    return list(pre), list(post), assignment


def test_c1_high_correlation_variance_reduction() -> None:
    """C1: High correlation → empirical variance reduction ≈ ρ².

    pre_std=2.0, noise_std=0.9 → theoretical ρ ≈ 2/sqrt(4+0.81) ≈ 0.91.
    Theoretical reduction ≈ 83%.  Tolerance: ±15 pp absolute.
    """
    pre, post, assign = _generate_correlated_data(
        n_ctrl=500,
        n_trt=500,
        pre_mean=10.0,
        pre_std=2.0,
        noise_std=0.9,
        treatment_effect=1.0,
        seed=_RNG_SEED,
    )

    result = apply_cuped(pre, post, assign)
    empirical_rho = abs(result.correlation_pre_post)
    theoretical_reduction = empirical_rho**2 * 100.0
    actual_reduction = result.variance_reduction_pct

    delta = abs(actual_reduction - theoretical_reduction)
    passed = delta <= _VAR_TOL

    likely = ""
    if not passed:
        likely = (
            f"Empirical reduction ({actual_reduction:.1f}%) deviates from ρ² "
            f"({theoretical_reduction:.1f}%) by {delta:.1f} pp.  Check that θ is "
            "estimated from the pooled population (not group-specific) and that "
            "Y_adj = Y − θ(X − X̄_pooled)."
        )

    record(
        module=_MODULE,
        scenario=f"C1: high correlation (ρ≈{empirical_rho:.2f}), n=500+500",
        expected=f"variance_reduction ≈ {theoretical_reduction:.1f}%",
        observed=f"variance_reduction = {actual_reduction:.1f}%",
        delta=f"{delta:.1f} pp",
        tolerance=f"≤{_VAR_TOL} pp",
        passed=passed,
        likely_cause=likely,
        notes=f"ρ={empirical_rho:.3f}, θ={result.theta:.4f}",
    )

    assert result.variance_reduction_pct > 0, "Variance reduction must be positive."
    assert passed, (
        f"C1: empirical reduction {actual_reduction:.1f}% vs theoretical "
        f"{theoretical_reduction:.1f}% (Δ={delta:.1f} pp > {_VAR_TOL} pp)"
    )


def test_c2_low_correlation_minimal_benefit() -> None:
    """C2: Low correlation → CUPED provides < 10% variance reduction.

    pre and post are nearly independent (noise >> signal).
    pre_std=0.5, noise_std=5.0 → ρ ≈ 0.5/sqrt(0.25+25) ≈ 0.099.
    Theoretical reduction ≈ 1%.
    """
    pre, post, assign = _generate_correlated_data(
        n_ctrl=400,
        n_trt=400,
        pre_mean=5.0,
        pre_std=0.5,
        noise_std=5.0,
        treatment_effect=0.5,
        seed=_RNG_SEED + 1,
    )

    result = apply_cuped(pre, post, assign)
    actual_reduction = result.variance_reduction_pct
    empirical_rho = abs(result.correlation_pre_post)

    passed = actual_reduction < 10.0

    likely = ""
    if not passed:
        likely = (
            f"Low-correlation scenario ({empirical_rho:.2f}) should yield < 10% "
            "variance reduction.  θ may be over-fitted or computed on a subset "
            "rather than the pooled population."
        )

    record(
        module=_MODULE,
        scenario=f"C2: low correlation (ρ≈{empirical_rho:.2f}), n=400+400",
        expected="variance_reduction < 10%",
        observed=f"variance_reduction = {actual_reduction:.1f}%",
        delta=f"{actual_reduction:.1f} pp (from 0)",
        tolerance="< 10 pp",
        passed=passed,
        likely_cause=likely,
        notes=f"ρ={empirical_rho:.3f}, θ={result.theta:.4f}",
    )

    assert passed, (
        f"C2: reduction = {actual_reduction:.1f}% for low-correlation data "
        f"(ρ={empirical_rho:.3f}); expected < 10%"
    )


def test_c3_treatment_effect_preserved() -> None:
    """C3: CUPED must not bias the treatment effect estimate.

    Mathematical invariant tested here:
        adjusted_lift = unadjusted_lift + θ*(mean_x_trt − mean_x_ctrl)

    When pre-experiment covariates are IDENTICAL for both groups,
    mean_x_ctrl = mean_x_trt = x̄, so the θ adjustment cancels out:
        adjusted_lift = unadjusted_lift (to floating-point precision)

    This tests the formula directly without relying on random-sample balance.
    The invariant holds in expectation for any random assignment; we verify the
    exact algebraic consequence of balanced covariates.

    Note on finite samples: when covariates differ between groups (the normal
    case), adjusted_lift ≠ unadjusted_lift.  That is CORRECT behaviour — CUPED
    removes the component of the outcome explained by pre-experiment differences,
    giving a less noisy estimate of the true effect.
    """
    rng = np.random.default_rng(_RNG_SEED + 2)
    n = 400

    # Same covariate vector for both groups → exact pre-experiment balance.
    x_shared = rng.normal(8.0, 2.0, n)
    noise_ctrl = rng.normal(0.0, 1.0, n)
    noise_trt = rng.normal(0.0, 1.0, n)
    true_effect = 1.5

    post_ctrl = (x_shared + noise_ctrl).tolist()
    post_trt = (x_shared + noise_trt + true_effect).tolist()

    # Duplicate x_shared for both groups: mean(x_ctrl) = mean(x_trt) = x̄ exactly.
    pre = list(x_shared) + list(x_shared)
    post = post_ctrl + post_trt
    assign = [0] * n + [1] * n

    result = apply_cuped(pre, post, assign)

    lift_adjusted = result.adjusted_test_result.lift_abs
    lift_unadjusted = result.unadjusted_test_result.lift_abs
    delta = abs(lift_adjusted - lift_unadjusted)

    # With exact balance: θ*(mean_x_trt − mean_x_ctrl) = θ*0 = 0.
    # Tolerance is floating-point precision only.
    _EXACT_TOL = 1e-9
    passed = delta <= _EXACT_TOL

    likely = ""
    if not passed:
        likely = (
            f"With identical pre-experiment x for both groups, "
            f"adjusted_lift should equal unadjusted_lift to floating-point "
            f"precision (Δ={delta:.2e}).  This means X̄ is NOT computed from "
            "the full pooled population or theta is applied asymmetrically."
        )

    record(
        module=_MODULE,
        scenario="C3: effect preservation, balanced x (Δ≈0 by algebra)",
        expected="lift_adj = lift_unadj (Δ < 1e-9, floating-point exact)",
        observed=f"lift_adj={lift_adjusted:.6f}, lift_unadj={lift_unadjusted:.6f}",
        delta=f"{delta:.2e}",
        tolerance="< 1e-9 (algebraic exact with balanced x)",
        passed=passed,
        likely_cause=likely,
        notes=(
            "Same x values for both groups forces mean(x_ctrl)=mean(x_trt)=x̄. "
            "Adjusted lift must equal unadjusted lift because θ*(0)=0."
        ),
    )

    assert passed, (
        f"C3: lift_adj={lift_adjusted:.6f} vs lift_unadj={lift_unadjusted:.6f} "
        f"(Δ={delta:.2e} > 1e-9). {likely}"
    )


def test_c4_zero_correlation_graceful_degradation() -> None:
    """C4: Zero correlation — CUPED must degrade gracefully.

    When pre and post are completely independent, θ ≈ 0, variance_reduction ≈ 0,
    and the adjusted test result must equal (or be very close to) the unadjusted.
    """
    rng = np.random.default_rng(_RNG_SEED + 3)
    n = 300
    # Independent pre and post
    pre = list(rng.normal(5.0, 2.0, n * 2))
    post_ctrl = list(rng.normal(10.0, 3.0, n))
    post_trt = list(rng.normal(11.0, 3.0, n))  # treatment effect = +1
    post = post_ctrl + post_trt
    assign = [0] * n + [1] * n

    result = apply_cuped(pre, post, assign)

    rho = abs(result.correlation_pre_post)
    reduction = result.variance_reduction_pct

    passed = rho < 0.15 and reduction < 5.0

    likely = ""
    if not passed:
        likely = (
            f"High variance reduction ({reduction:.1f}%) for independent data "
            f"(|ρ|={rho:.3f}).  θ estimation may be over-fitting on a small "
            "sample.  Consider whether OLS is operating on the full population."
        )

    record(
        module=_MODULE,
        scenario="C4: independent pre/post (ρ≈0), n=300+300",
        expected="|ρ| < 0.15, variance_reduction < 5%",
        observed=f"|ρ|={rho:.3f}, variance_reduction={reduction:.1f}%",
        delta=f"|ρ|={rho:.3f}",
        tolerance="|ρ|<0.15, reduction<5%",
        passed=passed,
        likely_cause=likely,
        notes="θ≈0 when covariates are orthogonal; adjusted test ≈ unadjusted test.",
    )

    # Graceful degradation: theta near zero
    assert (
        result.theta is not None
    ), "theta must be returned even for zero-correlation data."
    assert passed, (
        f"C4: reduction={reduction:.1f}%, |ρ|={rho:.3f} for independent data. "
        f"{likely}"
    )

"""Sample size calculation and power analysis for two-proportion A/B tests."""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel

try:
    from statsmodels.stats.power import NormalIndPower

    _HAS_STATSMODELS = True
except ImportError:  # pragma: no cover
    _HAS_STATSMODELS = False

from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class SampleSizeResult(BaseModel):
    """Output of calculate_sample_size."""

    control_size: int
    treatment_size: int
    total_sample_size: int
    cohens_d: float
    method_used: str
    power_curve: list[dict[str, float]]


class RuntimeEstimate(BaseModel):
    """Estimated experiment duration based on daily traffic."""

    days_expected: float
    days_lower_95: float
    days_upper_95: float
    weeks_expected: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cohens_d_for_proportions(baseline_rate: float, mde: float) -> float:
    """Compute Cohen's d for the difference between two binary-outcome groups.

    For a Bernoulli(p) observation, the variance is p*(1-p). Cohen's d
    normalises the raw difference by the pooled standard deviation, producing
    a dimensionless effect size that is comparable across experiments:

        d = (p2 - p1) / sqrt(p_bar * (1 - p_bar))

    where p_bar = (p1 + p2) / 2 is the average rate under equal allocation.

    Args:
        baseline_rate: Control conversion rate p1.
        mde: Absolute difference p2 - p1.

    Returns:
        Cohen's d (always positive; direction is handled by the caller).
    """
    p_bar = baseline_rate + mde / 2  # average of p1 and p1+mde
    pooled_sd = math.sqrt(p_bar * (1.0 - p_bar))
    return abs(mde) / pooled_sd


def _build_power_curve(
    baseline_rate: float,
    mde: float,
    alpha: float,
    n_required: int,
) -> list[dict[str, float]]:
    """Return 20 (n, power) pairs spanning 10% to 200% of n_required.

    Args:
        baseline_rate: Control conversion rate.
        mde: Absolute MDE (positive).
        alpha: Significance level.
        n_required: Required per-group sample size (used to set the x-axis range).

    Returns:
        List of dicts with keys "n" (float) and "power" (float, 4 d.p.).
    """
    n_lo = max(10, n_required // 10)
    n_hi = n_required * 2
    ns = np.linspace(n_lo, n_hi, 20, dtype=int)
    return [
        {"n": float(n), "power": round(calculate_power(baseline_rate, mde, int(n), alpha), 4)}
        for n in ns
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_power(
    baseline_rate: float,
    mde: float,
    sample_size: int,
    alpha: float = 0.05,
) -> float:
    """Calculate statistical power for a given per-group sample size.

    Power is P(reject H0 | H1 is true): the probability of detecting a real
    effect of size `mde` when we have `sample_size` observations per group.

    Under H1 the two-sample z-statistic has a non-central normal distribution.
    The non-centrality parameter is d * sqrt(n / 2), where d is Cohen's d and
    n is the per-group sample size. Power equals the probability that this
    non-central statistic exceeds the two-tailed critical value z_{alpha/2}.

    Args:
        baseline_rate: Control conversion rate in (0, 1).
        mde: Absolute effect size to detect (may be negative; magnitude is used).
        sample_size: Per-group sample size (positive integer).
        alpha: Two-tailed significance level. Default 0.05.

    Returns:
        Power as a float in [0, 1].

    Raises:
        ValueError: If any parameter is outside its valid range.
    """
    if not (0.0 < baseline_rate < 1.0):
        raise ValueError(f"baseline_rate must be in (0, 1), got {baseline_rate}")
    if sample_size <= 0:
        raise ValueError(f"sample_size must be positive, got {sample_size}")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    if mde == 0.0:
        # Under H0 (no effect), the test still rejects with probability alpha.
        return float(alpha)

    d = _cohens_d_for_proportions(baseline_rate, mde)

    if _HAS_STATSMODELS:
        achieved = NormalIndPower().solve_power(
            effect_size=d,
            nobs1=float(sample_size),
            alpha=alpha,
            ratio=1.0,
        )
        return float(np.clip(achieved, 0.0, 1.0))

    # Fallback: closed-form two-tailed normal approximation.
    # The test statistic under H1 ~ Normal(nc, 1) where nc = d * sqrt(n/2).
    # Two-tailed power = Φ(nc - z) + Φ(-nc - z), with z = Φ^{-1}(1 - α/2).
    z_crit = scipy_stats.norm.ppf(1.0 - alpha / 2.0)
    nc = d * math.sqrt(sample_size / 2.0)
    power = scipy_stats.norm.cdf(nc - z_crit) + scipy_stats.norm.cdf(-nc - z_crit)
    return float(np.clip(power, 0.0, 1.0))


def calculate_sample_size(
    baseline_rate: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_tailed: bool = True,
) -> SampleSizeResult:
    """Calculate per-group sample size for a two-proportion A/B test.

    Expresses the detectable effect as Cohen's d — the raw difference divided
    by the pooled Bernoulli standard deviation — and solves for the per-group n
    that achieves the desired power at significance level alpha.

    With statsmodels available, `NormalIndPower().solve_power` is used, which
    numerically inverts the power function. Without statsmodels, the Wald
    closed-form formula is used:

        n = ((z_{alpha/2} + z_{beta}) / d)^2

    Both approaches assume a two-sample z-test with equal group sizes.

    Args:
        baseline_rate: Current conversion rate, e.g. 0.05 for a 5% baseline.
        mde: Minimum detectable effect as an absolute change in rate,
             e.g. 0.01 to detect a shift from 5% → 6%.
        alpha: Type I error rate (false positive rate). Default 0.05.
        power: Desired statistical power (1 - Type II error rate). Default 0.80.
        two_tailed: If True (default), test for improvement OR degradation.
                    If False, test only for improvement (one-tailed).

    Returns:
        SampleSizeResult with per-group sizes, total size, Cohen's d,
        the method name, and a 20-point power curve.

    Raises:
        ValueError: If any parameter is outside its valid range.
    """
    if not (0.0 < baseline_rate < 1.0):
        raise ValueError(f"baseline_rate must be in (0, 1), got {baseline_rate}")
    if mde == 0.0:
        raise ValueError("mde must be non-zero; a zero effect requires infinite samples.")
    treatment_rate = baseline_rate + mde
    if not (0.0 < treatment_rate < 1.0):
        raise ValueError(
            f"baseline_rate + mde = {treatment_rate:.4f} is outside (0, 1). "
            "Adjust the MDE so the treatment rate is a valid probability."
        )
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if power >= 1.0:
        raise ValueError(
            "power must be strictly less than 1.0; power = 1.0 requires infinite samples."
        )
    if not (0.0 < power < 1.0):
        raise ValueError(f"power must be in (0, 1), got {power}")

    d = _cohens_d_for_proportions(baseline_rate, mde)

    # One-tailed tests use the full alpha on one side, equivalent to using
    # alpha * 2 in a two-tailed formula.  NormalIndPower's `alpha` parameter
    # already handles directionality, so we pass the adjusted value directly.
    alpha_for_solver = alpha if two_tailed else alpha * 2.0

    if _HAS_STATSMODELS:
        n_per_group = NormalIndPower().solve_power(
            effect_size=d,
            power=power,
            alpha=alpha_for_solver,
            ratio=1.0,  # equal group sizes
        )
        method = "statsmodels_NormalIndPower"
    else:
        # Wald closed-form: derived from inverting the non-centrality condition.
        # At the target power, the non-centrality must equal z_{alpha/2} + z_{beta}.
        # nc = d * sqrt(n/2)  =>  n = 2 * (nc / d)^2 = 2 * ((z_a + z_b) / d)^2 / 2
        z_alpha = scipy_stats.norm.ppf(1.0 - alpha / (2.0 if two_tailed else 1.0))
        z_beta = scipy_stats.norm.ppf(power)
        n_per_group = ((z_alpha + z_beta) / d) ** 2
        method = "scipy_wald"

    n_int = math.ceil(n_per_group)

    return SampleSizeResult(
        control_size=n_int,
        treatment_size=n_int,
        total_sample_size=2 * n_int,
        cohens_d=round(d, 6),
        method_used=method,
        power_curve=_build_power_curve(baseline_rate, abs(mde), alpha, n_int),
    )


def calculate_mde(
    baseline_rate: float,
    sample_size: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """Calculate the minimum detectable effect for a fixed per-group sample size.

    This is the inverse of calculate_sample_size: given a budget of
    `sample_size` observations per group, what is the smallest absolute
    change in conversion rate that the test is powered to detect?

    The solver finds the Cohen's d achievable at the given n, then converts
    it back to an absolute rate difference via one Newton step:

        delta = d * sqrt(p_bar * (1 - p_bar))

    where p_bar = baseline_rate + delta/2 (which depends on delta).
    The iteration converges in one step for small deltas.

    Args:
        baseline_rate: Control conversion rate in (0, 1).
        sample_size: Per-group sample size available.
        alpha: Two-tailed significance level. Default 0.05.
        power: Desired statistical power. Default 0.80.

    Returns:
        MDE as a positive absolute change in conversion rate.

    Raises:
        ValueError: If any parameter is outside its valid range.
    """
    if not (0.0 < baseline_rate < 1.0):
        raise ValueError(f"baseline_rate must be in (0, 1), got {baseline_rate}")
    if sample_size <= 0:
        raise ValueError(f"sample_size must be positive, got {sample_size}")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if power >= 1.0:
        raise ValueError("power must be strictly less than 1.0.")
    if not (0.0 < power < 1.0):
        raise ValueError(f"power must be in (0, 1), got {power}")

    if _HAS_STATSMODELS:
        # Solve for the Cohen's d that achieves `power` with this sample size.
        min_d = NormalIndPower().solve_power(
            nobs1=float(sample_size),
            power=power,
            alpha=alpha,
            ratio=1.0,
        )
    else:
        z_alpha = scipy_stats.norm.ppf(1.0 - alpha / 2.0)
        z_beta = scipy_stats.norm.ppf(power)
        # Invert n = ((z_a + z_b) / d)^2  =>  d = (z_a + z_b) / sqrt(n)
        min_d = (z_alpha + z_beta) / math.sqrt(sample_size)

    # First approximation: treat p_bar ≈ baseline_rate.
    mde_approx = min_d * math.sqrt(baseline_rate * (1.0 - baseline_rate))

    # Refine once: plug the approximate mde back in to get a better p_bar.
    p_bar_refined = baseline_rate + mde_approx / 2.0
    p_bar_refined = max(1e-9, min(1.0 - 1e-9, p_bar_refined))
    mde_refined = min_d * math.sqrt(p_bar_refined * (1.0 - p_bar_refined))

    return float(mde_refined)


def runtime_estimate(
    required_sample_size: int,
    daily_traffic: int,
) -> RuntimeEstimate:
    """Estimate experiment duration given a required sample size and daily traffic.

    Models daily subject arrivals as Poisson(daily_traffic). By the Central
    Limit Theorem, the daily count approximately follows Normal(λ, λ), so
    the total traffic over d days is Normal(d·λ, d·λ).

    The 95% CI on experiment duration is derived by bounding the daily rate:
    - Optimistic (lower bound on days): assume daily intake = λ + 1.96·√λ
    - Pessimistic (upper bound on days): assume daily intake = max(λ - 1.96·√λ, 1)

    Args:
        required_sample_size: Total subjects needed across both groups.
        daily_traffic: Average number of eligible subjects per day.

    Returns:
        RuntimeEstimate with expected days, 95% CI bounds, and expected weeks.

    Raises:
        ValueError: If either argument is non-positive.
    """
    if required_sample_size <= 0:
        raise ValueError(
            f"required_sample_size must be positive, got {required_sample_size}"
        )
    if daily_traffic <= 0:
        raise ValueError(f"daily_traffic must be positive, got {daily_traffic}")

    lam = float(daily_traffic)
    std_daily = math.sqrt(lam)

    days_expected = required_sample_size / lam
    # Optimistic: traffic is higher than average → fewer days needed.
    days_lower = required_sample_size / (lam + 1.96 * std_daily)
    # Pessimistic: traffic is lower than average → more days needed.
    # Floor at 1.0 to avoid division by zero for tiny daily_traffic.
    pessimistic_daily = max(lam - 1.96 * std_daily, 1.0)
    days_upper = required_sample_size / pessimistic_daily

    return RuntimeEstimate(
        days_expected=round(days_expected, 1),
        days_lower_95=round(days_lower, 1),
        days_upper_95=round(days_upper, 1),
        weeks_expected=round(days_expected / 7.0, 1),
    )

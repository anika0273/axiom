"""
Statistical hypothesis testing for A/B experiments.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When to use each test
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

run_proportion_test
    Binary outcome metric: did the event happen? (click, convert, sign-up,
    purchase).  Uses a two-proportion z-test under the normal approximation
    to the binomial.  Valid when both groups have >= 5 expected successes and
    failures (i.e. n >= 30 and conversion rate not close to 0 or 1).

run_mean_test
    Continuous or count outcome: revenue, session duration, pages viewed,
    items added.  Uses Welch's t-test (unequal variances), which is strictly
    more robust than Student's t-test because it does not assume σ_c = σ_t.
    Also appropriate for ratio metrics (revenue/user) when you have user-level
    values; see _delta_method_variance for the ratio-SE derivation.

run_cuped_proportion_test
    Same use-case as run_proportion_test, but with pre-experiment covariate
    data available per user.  CUPED (Controlled-experiment Using Pre-Experiment
    Data) reduces the variance of the estimator — meaning you reach the same
    power with fewer observations, or achieve higher power with the same n.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CUPED — how it works
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Variance of the A/B estimator is Var(ΔȲ) = Var(Ȳ_t) + Var(Ȳ_c).  Any
pre-experiment metric X that correlates with the outcome Y can be used to
construct a new estimator that has LOWER variance without changing the
expected value (no bias introduced).

The CUPED-adjusted outcome for user i is:

    Y_adj_i = Y_i − θ · (X_i − E[X])

where θ = Cov(Y, X) / Var(X) is the OLS coefficient from a pooled linear
regression of Y on X.  Taking the mean:

    E[Y_adj_g] = E[Y_g] − θ · (E[X_g] − E[X])

Because random assignment ensures E[X_c] ≈ E[X_t] ≈ E[X], the adjustment
subtracts the same constant from both groups, so the difference is unchanged:

    E[Y_adj_t] − E[Y_adj_c] = E[Y_t] − E[Y_c]   ← unbiased

The variance is:

    Var(Y_adj_i) = Var(Y_i) − θ² · Var(X_i) = Var(Y_i) · (1 − ρ²)

where ρ = Corr(Y, X).  A covariate with ρ = 0.4 reduces variance by 16%;
ρ = 0.7 reduces it by 49%.  Good choices: prior-period conversion flag,
number of past sessions, account age.

ASSUMPTION on covariate arrays: the caller must provide covariate values in
the same user-order as outcomes.  Because aggregate successes are passed (not
per-user outcomes), this implementation synthesises binary arrays as
[1…1, 0…0] (converters first).  For best results, sort each group's
covariate array to match the same converter-first ordering, or pass user-
level (outcome, covariate) pairs through a wrapper that calls this function.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Delta method for ratio metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

See _delta_method_variance below.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from pydantic import BaseModel
from scipy import stats as scipy_stats
from scipy.stats import linregress
from statsmodels.stats.proportion import proportions_ztest

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class TestResult(BaseModel):
    """Outcome of a single hypothesis test."""

    is_significant: bool
    p_value: float
    confidence_interval: tuple[float, float]  # 95% CI on the difference
    lift_pct: float  # relative lift: (treatment − control) / control × 100
    lift_abs: float  # absolute lift: treatment_metric − control_metric
    test_statistic: float
    test_type: Literal["z-test", "t-test", "cuped-z"]
    sample_warnings: list[str]  # e.g. ["small sample", "low conversions"]
    interpretation: str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _proportion_warnings(
    successes_c: int,
    n_c: int,
    successes_t: int,
    n_t: int,
) -> list[str]:
    """Collect data-quality warnings for a proportion test."""
    warnings: list[str] = []
    if n_c < 30 or n_t < 30:
        warnings.append("small sample")
    if successes_c < 5 or successes_t < 5:
        warnings.append("low conversions")
    if successes_c == 0 or successes_t == 0:
        warnings.append("zero events in one or both groups")
    return warnings


def _mean_warnings(values_c: np.ndarray, values_t: np.ndarray) -> list[str]:
    """Collect data-quality warnings for a mean test."""
    warnings: list[str] = []
    if len(values_c) < 30 or len(values_t) < 30:
        warnings.append("small sample")
    if np.std(values_c) == 0.0 or np.std(values_t) == 0.0:
        warnings.append("zero variance")
    return warnings


def _proportion_ci(
    successes_c: int,
    n_c: int,
    successes_t: int,
    n_t: int,
    alpha: float,
) -> tuple[float, float]:
    """Wald CI for the difference in proportions (unpooled SE).

    The CI uses the unpooled standard error — each group's own p*(1-p)/n —
    because pooling under H0 is only correct for the test statistic, not for
    the interval estimate.
    """
    p_c = successes_c / n_c
    p_t = successes_t / n_t
    delta = p_t - p_c
    # Clamp rates away from 0/1 to avoid SE = 0 for degenerate inputs.
    p_c_s = max(p_c, 1 / (2 * n_c))
    p_t_s = max(p_t, 1 / (2 * n_t))
    se = math.sqrt(p_c_s * (1 - p_c_s) / n_c + p_t_s * (1 - p_t_s) / n_t)
    z_crit = scipy_stats.norm.ppf(1.0 - alpha / 2.0)
    return (delta - z_crit * se, delta + z_crit * se)


def _build_interpretation(
    is_significant: bool,
    lift_pct: float,
    lift_abs: float,
    p_value: float,
    test_type: str,
    alpha: float,
) -> str:
    """Produce a human-readable verdict string."""
    if not is_significant:
        return f"No significant difference detected (p={p_value:.3f}, α={alpha})"
    metric = "mean" if test_type == "t-test" else "conversion"
    direction = "improved" if lift_pct > 0 else "degraded"
    sign = "+" if lift_abs > 0 else ""
    return (
        f"Treatment {metric} {direction} by {abs(lift_pct):.1f}% relative "
        f"({sign}{lift_abs:.4f} absolute) "
        f"(p={p_value:.3f}, significant at α={alpha})"
    )


def _delta_method_variance(
    numerator: np.ndarray,
    denominator: np.ndarray,
) -> tuple[float, float]:
    """Estimate the mean and variance of a ratio metric using the delta method.

    For a ratio estimator R = Σa_i / Σb_i (e.g. total revenue / number of
    users), the delta method linearises R around (μ_a, μ_b):

        R ≈ μ_a/μ_b + (a_i − μ_a)/μ_b − μ_a·(b_i − μ_b)/μ_b²

    Taking the variance of this linear approximation:

        Var(R) ≈ (1/μ_b²)·[Var(a) + R²·Var(b) − 2R·Cov(a, b)] / n

    This is more accurate than naïvely computing per-user a_i/b_i and taking
    the sample variance, especially when denominator values are small or
    highly variable (sessions per user, items per order, etc.).

    Args:
        numerator: Per-user numerator values (e.g. revenue per user).
        denominator: Per-user denominator values (e.g. sessions per user).

    Returns:
        (ratio_mean, ratio_variance) — variance suitable for a z-test SE.

    Raises:
        ValueError: If the mean denominator is zero.
    """
    mu_a = np.mean(numerator)
    mu_b = np.mean(denominator)
    if mu_b == 0.0:
        raise ValueError("Mean denominator is zero; ratio metric is undefined.")

    n = len(numerator)
    ratio = mu_a / mu_b
    var_a = np.var(numerator, ddof=1)
    var_b = np.var(denominator, ddof=1)
    cov_ab = np.cov(numerator, denominator, ddof=1)[0, 1]

    # Delta method variance: each term represents one component of the
    # linearised Taylor expansion (numerator variance, denominator variance,
    # their covariance cross-term).
    delta_var = (var_a + ratio**2 * var_b - 2 * ratio * cov_ab) / (mu_b**2 * n)
    return float(ratio), float(delta_var)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def run_proportion_test(
    control_successes: int,
    control_n: int,
    treatment_successes: int,
    treatment_n: int,
    alpha: float = 0.05,
) -> TestResult:
    """Run a two-proportion z-test for a binary outcome metric.

    Uses statsmodels' proportions_ztest with the pooled proportion under H0.
    The confidence interval uses the unpooled Wald estimator because pooling
    is appropriate only for the test statistic, not the interval.

    Args:
        control_successes: Number of successes (events) in the control group.
        control_n: Total observations in the control group.
        treatment_successes: Number of successes in the treatment group.
        treatment_n: Total observations in the treatment group.
        alpha: Two-tailed significance level. Default 0.05.

    Returns:
        TestResult with p-value, CI, lift, and a human-readable interpretation.

    Raises:
        ValueError: If any count is negative, successes exceed n, or n is zero.
    """
    for label, s, n in [
        ("control", control_successes, control_n),
        ("treatment", treatment_successes, treatment_n),
    ]:
        if n <= 0:
            raise ValueError(f"{label}_n must be positive, got {n}")
        if s < 0:
            raise ValueError(f"{label}_successes must be non-negative, got {s}")
        if s > n:
            raise ValueError(f"{label}_successes ({s}) exceeds {label}_n ({n})")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    p_c = control_successes / control_n
    p_t = treatment_successes / treatment_n

    # Handle all-zero case: no information to separate groups.
    if control_successes == 0 and treatment_successes == 0:
        warnings = _proportion_warnings(
            control_successes, control_n, treatment_successes, treatment_n
        )
        return TestResult(
            is_significant=False,
            p_value=1.0,
            confidence_interval=(0.0, 0.0),
            lift_pct=0.0,
            lift_abs=0.0,
            test_statistic=0.0,
            test_type="z-test",
            sample_warnings=warnings,
            interpretation="No significant difference detected (p=1.000, α=0.05) — zero events in both groups.",
        )

    # proportions_ztest takes (count, nobs); order is [treatment, control]
    # so the z-statistic is positive when treatment > control.
    z_stat, p_value = proportions_ztest(
        count=np.array([treatment_successes, control_successes]),
        nobs=np.array([treatment_n, control_n]),
        alternative="two-sided",
    )

    ci = _proportion_ci(
        control_successes, control_n, treatment_successes, treatment_n, alpha
    )

    lift_abs = p_t - p_c
    lift_pct = (lift_abs / p_c * 100.0) if p_c > 0.0 else 0.0
    is_significant = p_value < alpha

    return TestResult(
        is_significant=is_significant,
        p_value=float(round(p_value, 6)),
        confidence_interval=ci,
        lift_pct=float(round(lift_pct, 4)),
        lift_abs=float(round(lift_abs, 6)),
        test_statistic=float(round(z_stat, 6)),
        test_type="z-test",
        sample_warnings=_proportion_warnings(
            control_successes, control_n, treatment_successes, treatment_n
        ),
        interpretation=_build_interpretation(
            is_significant, lift_pct, lift_abs, p_value, "z-test", alpha
        ),
    )


def run_mean_test(
    control_values: np.ndarray,
    treatment_values: np.ndarray,
    alpha: float = 0.05,
) -> TestResult:
    """Run Welch's t-test for a continuous or count outcome metric.

    Welch's t-test (equal_var=False) does not assume σ_c = σ_t, making it
    robust to unequal variances and group sizes.  The confidence interval is
    constructed from the Welch–Satterthwaite degrees of freedom.

    For ratio metrics (revenue / sessions), compute per-user values before
    passing them in, or use _delta_method_variance to get a more accurate SE.

    Args:
        control_values: Array of per-user metric values in the control group.
        treatment_values: Array of per-user metric values in the treatment group.
        alpha: Two-tailed significance level. Default 0.05.

    Returns:
        TestResult with p-value, CI, lift, and interpretation.

    Raises:
        ValueError: If either array is empty or alpha is invalid.
    """
    if len(control_values) == 0 or len(treatment_values) == 0:
        raise ValueError("control_values and treatment_values must be non-empty.")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    n_c = len(control_values)
    n_t = len(treatment_values)

    result = scipy_stats.ttest_ind(treatment_values, control_values, equal_var=False)
    t_stat: float = float(result.statistic)
    p_value: float = float(result.pvalue)
    df: float = float(result.df)

    mean_c = float(np.mean(control_values))
    mean_t = float(np.mean(treatment_values))
    lift_abs = mean_t - mean_c
    lift_pct = (lift_abs / abs(mean_c) * 100.0) if mean_c != 0.0 else 0.0

    # Welch CI: use per-group sample variances (not pooled).
    se = math.sqrt(
        float(np.var(treatment_values, ddof=1)) / n_t
        + float(np.var(control_values, ddof=1)) / n_c
    )
    t_crit = scipy_stats.t.ppf(1.0 - alpha / 2.0, df=df)
    ci = (lift_abs - t_crit * se, lift_abs + t_crit * se)

    is_significant = p_value < alpha

    return TestResult(
        is_significant=is_significant,
        p_value=float(round(p_value, 6)),
        confidence_interval=ci,
        lift_pct=float(round(lift_pct, 4)),
        lift_abs=float(round(lift_abs, 6)),
        test_statistic=float(round(t_stat, 6)),
        test_type="t-test",
        sample_warnings=_mean_warnings(control_values, treatment_values),
        interpretation=_build_interpretation(
            is_significant, lift_pct, lift_abs, p_value, "t-test", alpha
        ),
    )


def run_cuped_proportion_test(
    control_successes: int,
    control_n: int,
    control_covariates: np.ndarray,
    treatment_successes: int,
    treatment_n: int,
    treatment_covariates: np.ndarray,
    alpha: float = 0.05,
) -> TestResult:
    """Run a CUPED-adjusted z-test for a binary outcome with pre-experiment data.

    Reduces estimator variance by removing the component of each user's
    outcome that is explained by their pre-experiment behaviour.  The
    adjustment is linear:

        Y_adj_i = Y_i − θ · (X_i − X̄_pooled)

    where θ = Cov(Y, X) / Var(X) is estimated via OLS on the pooled data.
    The adjusted group means are tested with a standard z-test.

    Variance reduction is proportional to ρ(Y, X)²: a covariate with
    ρ = 0.5 reduces variance by 25%, shortening required runtime accordingly.

    Caller convention: control_covariates[i] must correspond to the i-th user;
    the first control_successes entries are treated as converters.  See the
    module docstring for details.

    Args:
        control_successes: Conversions in the control group.
        control_n: Total users in the control group.
        control_covariates: Per-user pre-experiment covariate (length == control_n).
        treatment_successes: Conversions in the treatment group.
        treatment_n: Total users in the treatment group.
        treatment_covariates: Per-user covariate (length == treatment_n).
        alpha: Two-tailed significance level. Default 0.05.

    Returns:
        TestResult with CUPED-adjusted p-value, CI, and lift.

    Raises:
        ValueError: If covariate array lengths don't match n, counts are invalid,
                    or alpha is out of range.
    """
    for label, s, n, cov in [
        ("control", control_successes, control_n, control_covariates),
        ("treatment", treatment_successes, treatment_n, treatment_covariates),
    ]:
        if n <= 0:
            raise ValueError(f"{label}_n must be positive, got {n}")
        if s < 0:
            raise ValueError(f"{label}_successes must be non-negative, got {s}")
        if s > n:
            raise ValueError(f"{label}_successes ({s}) exceeds {label}_n ({n})")
        if len(cov) != n:
            raise ValueError(
                f"len({label}_covariates)={len(cov)} must equal {label}_n={n}"
            )
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    # Synthesise binary outcome vectors: converters occupy the first positions.
    # theta estimated from pooled regression captures the within-experiment
    # covariate-outcome relationship.
    y_c = np.concatenate(
        [
            np.ones(control_successes),
            np.zeros(control_n - control_successes),
        ]
    )
    y_t = np.concatenate(
        [
            np.ones(treatment_successes),
            np.zeros(treatment_n - treatment_successes),
        ]
    )

    y_pooled = np.concatenate([y_c, y_t])
    x_pooled = np.concatenate([control_covariates, treatment_covariates])
    x_bar_pooled = float(np.mean(x_pooled))

    # OLS: θ minimises E[(Y − θX)²], reducing Var(Y_adj) = Var(Y)·(1 − ρ²).
    slope, _intercept, r_value, _p_reg, _se_reg = linregress(x_pooled, y_pooled)
    theta = float(slope)

    # Per-user adjusted outcomes for each group.
    y_c_adj = y_c - theta * (control_covariates - x_bar_pooled)
    y_t_adj = y_t - theta * (treatment_covariates - x_bar_pooled)

    # Group means and variances of adjusted outcomes.
    mean_c_adj = float(np.mean(y_c_adj))
    mean_t_adj = float(np.mean(y_t_adj))
    var_c_adj = float(np.var(y_c_adj, ddof=1))
    var_t_adj = float(np.var(y_t_adj, ddof=1))

    diff_adj = mean_t_adj - mean_c_adj
    se_adj = math.sqrt(var_c_adj / control_n + var_t_adj / treatment_n)

    if se_adj == 0.0:
        z_stat, p_value = 0.0, 1.0
    else:
        z_stat = diff_adj / se_adj
        # Two-tailed p-value from the standard normal.
        p_value = float(2.0 * scipy_stats.norm.sf(abs(z_stat)))

    z_crit = scipy_stats.norm.ppf(1.0 - alpha / 2.0)
    ci = (diff_adj - z_crit * se_adj, diff_adj + z_crit * se_adj)

    # Lift is reported on raw (unadjusted) rates for interpretability.
    p_c_raw = control_successes / control_n
    p_t_raw = treatment_successes / treatment_n
    lift_abs = p_t_raw - p_c_raw
    lift_pct = (lift_abs / p_c_raw * 100.0) if p_c_raw > 0.0 else 0.0

    is_significant = p_value < alpha

    warnings = _proportion_warnings(
        control_successes, control_n, treatment_successes, treatment_n
    )
    if r_value**2 < 0.01:
        # Covariate explains < 1% of outcome variance; CUPED adds little.
        warnings.append("low covariate correlation, minimal CUPED variance reduction")

    return TestResult(
        is_significant=is_significant,
        p_value=float(round(p_value, 6)),
        confidence_interval=ci,
        lift_pct=float(round(lift_pct, 4)),
        lift_abs=float(round(lift_abs, 6)),
        test_statistic=float(round(z_stat, 6)),
        test_type="cuped-z",
        sample_warnings=warnings,
        interpretation=_build_interpretation(
            is_significant, lift_pct, lift_abs, p_value, "cuped-z", alpha
        ),
    )

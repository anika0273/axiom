"""
CUPED — Controlled-experiment Using Pre-Experiment Data
=======================================================

CUPED is a variance-reduction technique for A/B tests.  The core idea is
straightforward: if a user's pre-experiment behaviour (e.g. last week's
purchase count) predicts their experiment-period behaviour, you can subtract
out the predictable component and be left with a lower-variance signal.

The maths in one paragraph
--------------------------
For each user i, define the CUPED-adjusted outcome:

    Y_adj_i = Y_i − θ · (X_i − X̄)

where X_i is the pre-experiment metric, X̄ is its overall mean, and θ is
chosen to minimise Var(Y_adj):

    θ = Cov(X, Y) / Var(X)   ← OLS coefficient (see _estimate_theta)

Because θ is derived from a least-squares regression, it is the unique value
that minimises the expected squared residual.  Subtracting θ·(X_i − X̄) from
every observation does not change the expected value of the difference between
treatment and control (since random assignment ensures E[X_c] ≈ E[X_t]).
It does, however, shrink the variance of each group's mean:

    Var(Y_adj) = Var(Y) · (1 − ρ²)

where ρ = Corr(X, Y).  Variance reduction is therefore approximately ρ²:
a pre-post correlation of 0.5 gives a 25% reduction; 0.7 gives 49%; 0.9
gives 81%.  This translates directly into narrower confidence intervals and
shorter experiment runtimes needed to reach a given power.

When to use CUPED
-----------------
- The pre-experiment metric is the same type as the experiment metric
  (e.g. last month's revenue predicts this month's revenue well).
- |ρ| ≥ 0.3 (otherwise the benefit is marginal).
- Assignment is random — CUPED does not fix confounded experiments.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel

from app.stats.testing import TestResult, run_mean_test


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CUPEDGroupSummary(BaseModel):
    """Per-group descriptive statistics, both raw and CUPED-adjusted."""

    group_name: Literal["control", "treatment"]
    n_users: int
    pre_mean: float
    post_mean: float
    adjusted_mean: float


class CUPEDResult(BaseModel):
    """Full output of apply_cuped: both test results, diagnostics, and summaries."""

    adjusted_test_result: TestResult
    unadjusted_test_result: TestResult
    theta: float
    variance_reduction_pct: float
    correlation_pre_post: float
    recommendation: str
    control_summary: CUPEDGroupSummary
    treatment_summary: CUPEDGroupSummary


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_and_convert(
    pre: list[float],
    post: list[float],
    assignment: list[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate inputs and return typed numpy arrays.

    Args:
        pre: Pre-experiment per-user metric values.
        post: Experiment-period per-user metric values.
        assignment: Group assignment (0 = control, 1 = treatment).

    Returns:
        (x, y, a) — numpy float64 arrays of the same length.

    Raises:
        ValueError: If lengths mismatch, values are invalid, assignments are
                    out of range, or either group is empty.
    """
    if not (len(pre) == len(post) == len(assignment)):
        raise ValueError(
            f"pre_experiment_metric, experiment_metric, and treatment_assignment "
            f"must have the same length. Got lengths "
            f"{len(pre)}, {len(post)}, {len(assignment)}."
        )
    if len(pre) == 0:
        raise ValueError("Input arrays must not be empty.")

    x = np.asarray(pre, dtype=float)
    y = np.asarray(post, dtype=float)
    a = np.asarray(assignment, dtype=int)

    if not np.all(np.isfinite(x)):
        raise ValueError(
            "pre_experiment_metric contains NaN or Inf values. "
            "Remove or impute these before calling apply_cuped."
        )
    if not np.all(np.isfinite(y)):
        raise ValueError(
            "experiment_metric contains NaN or Inf values. "
            "Remove or impute these before calling apply_cuped."
        )
    if not np.all((a == 0) | (a == 1)):
        bad = np.unique(a[~((a == 0) | (a == 1))]).tolist()
        raise ValueError(
            f"treatment_assignment must contain only 0 or 1. "
            f"Found unexpected values: {bad}"
        )
    if not np.any(a == 0):
        raise ValueError(
            "No control users found (treatment_assignment has no 0s)."
        )
    if not np.any(a == 1):
        raise ValueError(
            "No treatment users found (treatment_assignment has no 1s)."
        )

    return x, y, a


def _estimate_theta(x: np.ndarray, y: np.ndarray) -> float:
    """Estimate the CUPED coefficient θ via OLS on the full user population.

    θ is the coefficient that minimises the sum of squared residuals in the
    linear model Y = θ·X + ε (centred at the mean):

        θ = Σ(Xᵢ − X̄)(Yᵢ − Ȳ) / Σ(Xᵢ − X̄)²

    This is the standard OLS slope formula.  The numerator is the sample
    covariance (times n) and the denominator is the sample variance (times n),
    so the n cancels and this is purely a numpy dot-product operation — no
    scipy dependency needed.

    Args:
        x: Pre-experiment metric array (pooled across both groups).
        y: Experiment metric array (pooled across both groups).

    Returns:
        θ as a float.  Returns 0.0 if Var(x) == 0 (constant covariate).
    """
    x_c = x - x.mean()
    denom = float(np.dot(x_c, x_c))  # Σ(Xᵢ − X̄)²

    if denom == 0.0:
        # Constant covariate carries no information; CUPED has no effect.
        return 0.0

    numer = float(np.dot(x_c, y - y.mean()))  # Σ(Xᵢ − X̄)(Yᵢ − Ȳ)
    return numer / denom


def _safe_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Return Pearson correlation, or 0.0 if either array has zero variance."""
    if np.var(x) == 0.0 or np.var(y) == 0.0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def recommend_cuped(correlation: float) -> str:
    """Return a plain-English recommendation based on pre-post correlation.

    Variance reduction from CUPED ≈ ρ², so the recommendation is based on
    how much of the outcome's variance the pre-experiment metric explains.

    Args:
        correlation: Pearson correlation between pre-experiment and
                     experiment metric.  Sign is ignored; only |ρ| matters.

    Returns:
        A recommendation string describing whether to use CUPED and why.
    """
    abs_r = abs(correlation)
    # Variance reduction is r^2 (see module docstring for derivation)
    variance_reduction = abs_r ** 2 * 100.0

    if abs_r < 0.1:
        return (
            f"CUPED is unlikely to help (|r| = {abs_r:.2f}, expected variance "
            f"reduction < 1%). Use a standard hypothesis test."
        )
    if abs_r < 0.3:
        return (
            f"Modest benefit from CUPED (|r| = {abs_r:.2f}, ~{variance_reduction:.0f}% "
            f"variance reduction). CUPED may slightly reduce required sample size."
        )
    if abs_r < 0.5:
        return (
            f"Good candidate for CUPED (|r| = {abs_r:.2f}, ~{variance_reduction:.0f}% "
            f"variance reduction). Use CUPED to improve statistical power."
        )
    return (
        f"CUPED is strongly recommended (|r| = {abs_r:.2f}, ~{variance_reduction:.0f}% "
        f"variance reduction). Significant improvement in statistical power expected."
    )


def estimate_variance_reduction(
    pre_experiment_metric: list[float],
    experiment_metric: list[float],
) -> float:
    """Estimate the variance reduction achievable by CUPED, as a percentage.

    Variance reduction ≈ ρ² × 100, because:

        Var(Y_adj) = Var(Y − θ(X − X̄))
                   = Var(Y) − 2θ·Cov(Y, X) + θ²·Var(X)
                   = Var(Y) − [Cov(X, Y)]²/Var(X)    [substituting θ = Cov/Var]
                   = Var(Y) · (1 − ρ²)

    So the fraction of variance removed equals ρ², regardless of the
    scale of X or Y.  A correlation of 0.5 → 25% reduction; 0.9 → 81%.

    Args:
        pre_experiment_metric: Per-user pre-experiment metric values.
        experiment_metric: Per-user experiment-period metric values.

    Returns:
        Estimated variance reduction as a percentage in [0, 100].

    Raises:
        ValueError: If arrays have different lengths or contain NaN/Inf.
    """
    if len(pre_experiment_metric) != len(experiment_metric):
        raise ValueError(
            f"pre_experiment_metric (len={len(pre_experiment_metric)}) and "
            f"experiment_metric (len={len(experiment_metric)}) must have the same length."
        )

    x = np.asarray(pre_experiment_metric, dtype=float)
    y = np.asarray(experiment_metric, dtype=float)

    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError(
            "Arrays contain NaN or Inf values. Remove or impute before calling "
            "estimate_variance_reduction."
        )

    r = _safe_correlation(x, y)
    return float(max(0.0, r ** 2 * 100.0))


def apply_cuped(
    pre_experiment_metric: list[float],
    experiment_metric: list[float],
    treatment_assignment: list[int],
) -> CUPEDResult:
    """Apply CUPED variance reduction to user-level experiment data.

    Estimates θ from the pooled population, computes CUPED-adjusted outcomes,
    and runs both adjusted and unadjusted Welch t-tests for comparison.  Also
    reports diagnostic statistics (θ, empirical variance reduction, ρ) and a
    recommendation string.

    Args:
        pre_experiment_metric: Per-user pre-experiment metric values
                                (e.g. last month's revenue).
        experiment_metric: Per-user experiment-period metric values
                           (e.g. this month's revenue).
        treatment_assignment: Per-user group assignment — 0 for control,
                              1 for treatment.  Must have the same length
                              as the metric arrays.

    Returns:
        CUPEDResult containing both test results, θ, variance reduction,
        correlation, recommendation, and per-group summaries.

    Raises:
        ValueError: If inputs are invalid (see _validate_and_convert).

    Example:
        A small illustrative dataset where post ≈ 2 × pre, making θ = 2 exactly:

            pre        = [1, 2, 3, 4, 5,   1, 2, 3, 4, 5]  ← same pre for both groups
            post       = [2, 4, 6, 8, 10,  3, 5, 7, 9, 11] ← treatment +1 throughout
            assignment = [0, 0, 0, 0, 0,   1, 1, 1, 1, 1]

        x̄ = 3.0.  Using the OLS formula:
            θ = Σ(xᵢ−3)(yᵢ−ȳ) / Σ(xᵢ−3)² = 4.0 / 2.0 = 2.0

        Adjusted outcomes:
            control:   yᵢ − 2(xᵢ − 3) = [2−2(-2), 4−2(-1), 6−0, 8−2, 10−4] = [6,6,6,6,6]
            treatment: yᵢ − 2(xᵢ − 3) = [3+4, 5+2, 7+0, 9−2, 11−4]          = [7,7,7,7,7]

        Within-group variance collapses to zero (each group perfectly explained
        by the covariate), and the lift of 1.0 is preserved.
    """
    x, y, a = _validate_and_convert(
        pre_experiment_metric, experiment_metric, treatment_assignment
    )

    ctrl_mask = a == 0
    trt_mask = a == 1

    # ── Estimate theta via OLS (see _estimate_theta for formula) ────────────
    theta = _estimate_theta(x, y)

    # ── CUPED adjustment: subtract the part of Y explained by X ─────────────
    # Y_adj_i = Y_i − θ · (X_i − X̄).  When θ = 0 (constant covariate or
    # zero correlation), Y_adj = Y unchanged — CUPED degrades gracefully.
    x_bar = x.mean()
    y_adj = y - theta * (x - x_bar)

    # ── Split into groups ───────────────────────────────────────────────────
    y_ctrl = y[ctrl_mask]
    y_trt = y[trt_mask]
    y_ctrl_adj = y_adj[ctrl_mask]
    y_trt_adj = y_adj[trt_mask]

    # ── Hypothesis tests (reuse existing infrastructure) ────────────────────
    unadjusted_result = run_mean_test(y_ctrl, y_trt)
    adjusted_result = run_mean_test(y_ctrl_adj, y_trt_adj)

    # ── Diagnostics ─────────────────────────────────────────────────────────
    var_y = float(np.var(y, ddof=1))
    var_y_adj = float(np.var(y_adj, ddof=1))

    # Empirical variance reduction: fraction of total variance removed by the
    # covariate adjustment.  Theoretically equals ρ²; computed empirically here
    # to reflect the actual data rather than the population estimate.
    if var_y == 0.0:
        variance_reduction_pct = 0.0
    else:
        variance_reduction_pct = float(max(0.0, (1.0 - var_y_adj / var_y) * 100.0))

    correlation = _safe_correlation(x, y)
    recommendation = recommend_cuped(correlation)

    # ── Group summaries ─────────────────────────────────────────────────────
    control_summary = CUPEDGroupSummary(
        group_name="control",
        n_users=int(ctrl_mask.sum()),
        pre_mean=float(round(x[ctrl_mask].mean(), 6)),
        post_mean=float(round(y_ctrl.mean(), 6)),
        adjusted_mean=float(round(y_ctrl_adj.mean(), 6)),
    )
    treatment_summary = CUPEDGroupSummary(
        group_name="treatment",
        n_users=int(trt_mask.sum()),
        pre_mean=float(round(x[trt_mask].mean(), 6)),
        post_mean=float(round(y_trt.mean(), 6)),
        adjusted_mean=float(round(y_trt_adj.mean(), 6)),
    )

    return CUPEDResult(
        adjusted_test_result=adjusted_result,
        unadjusted_test_result=unadjusted_result,
        theta=float(round(theta, 6)),
        variance_reduction_pct=float(round(variance_reduction_pct, 4)),
        correlation_pre_post=float(round(correlation, 6)),
        recommendation=recommendation,
        control_summary=control_summary,
        treatment_summary=treatment_summary,
    )

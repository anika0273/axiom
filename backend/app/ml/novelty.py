"""
Novelty effect detection for A/B experiments.

Distinguishes four trajectory patterns in daily treatment effect estimates:

- STABLE:       Effect is flat; safe to make shipping decision.
- NOVELTY:      Effect starts high and decays — users are excited by newness,
                not genuine value. Wait for steady-state before deciding.
- LEARNING:     Effect starts low and grows — users are adopting over time.
                Wait for the curve to plateau before deciding.
- INSUFFICIENT: Fewer than 7 days of data; no pattern can be identified.

Usage::

    trajectory = analyze_effect_trajectory(daily_lift, daily_se, days_running=14)
    print(trajectory.recommendation)
    # "Novelty effect detected. Wait 8 days for steady-state."
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

_MIN_DAYS = 7
_SLOPE_NEAR_ZERO = 0.001  # |slope| below this + CI overlaps zero → STABLE
_LIFT_CLIP = 1.0  # projected_stable_lift is clamped to [-1, 1]
_SE_EPSILON = 1e-6  # replaces zero standard errors


@dataclass
class EffectTrajectory:
    """Result of analyze_effect_trajectory."""

    pattern: Literal["STABLE", "NOVELTY", "LEARNING", "INSUFFICIENT"]
    slope: float
    slope_ci: tuple[float, float]
    initial_lift: float
    projected_stable_lift: float
    days_to_stable: int | None
    confidence: Literal["low", "medium", "high"]
    recommendation: str


def analyze_effect_trajectory(
    daily_lift: pd.Series,
    daily_se: pd.Series,
    days_running: int,
) -> EffectTrajectory:
    """Classify the trajectory of a treatment effect over time.

    Uses weighted linear regression (weights = 1/se²) to estimate the rate of
    change per day.  Days with smaller standard errors contribute more to the
    fit — this is the appropriate inverse-variance weighting for meta-analysis.

    Args:
        daily_lift: Daily treatment effect estimates (one per day).
        daily_se:   Daily standard errors corresponding to each lift estimate.
        days_running: Total days the experiment has been running.

    Returns:
        EffectTrajectory with pattern classification, slope, projections, and
        a plain-English recommendation.
    """
    n = len(daily_lift)

    if n < _MIN_DAYS:
        return EffectTrajectory(
            pattern="INSUFFICIENT",
            slope=0.0,
            slope_ci=(0.0, 0.0),
            initial_lift=float(daily_lift.iloc[0]) if n > 0 else 0.0,
            projected_stable_lift=float(daily_lift.mean()) if n > 0 else 0.0,
            days_to_stable=None,
            confidence="low",
            recommendation="Insufficient data. Run experiment at least 7 days.",
        )

    # Replace zero SEs to avoid division by zero in weight computation.
    se = daily_se.copy().astype(float)
    if (se == 0.0).any():
        logger.warning(
            "daily_se contains %d zero(s); replacing with epsilon=%s",
            int((se == 0.0).sum()),
            _SE_EPSILON,
        )
        se = se.replace(0.0, _SE_EPSILON)

    lift = daily_lift.astype(float).values
    days = np.arange(1, n + 1, dtype=float)
    # Weights: 1/se² — days with more data (lower SE) carry more influence.
    weights = 1.0 / se.values**2

    slope, intercept, slope_se = _weighted_linregress(days, lift, weights)

    t_crit = stats.t.ppf(0.975, df=n - 2)
    slope_ci = (slope - t_crit * slope_se, slope + t_crit * slope_se)

    initial_lift = float(intercept + slope * 1.0)  # fitted value at day 1
    current_mean = float(np.average(lift, weights=weights))

    pattern, projected_lift, days_to_stable = _classify_pattern(
        slope=slope,
        slope_ci=slope_ci,
        initial_lift=initial_lift,
        current_mean=current_mean,
        days_running=days_running,
    )

    projected_stable_lift = float(np.clip(projected_lift, -_LIFT_CLIP, _LIFT_CLIP))
    confidence = _compute_confidence(n=n, slope_ci=slope_ci)
    recommendation = _make_recommendation(pattern, days_to_stable)

    return EffectTrajectory(
        pattern=pattern,
        slope=float(slope),
        slope_ci=(float(slope_ci[0]), float(slope_ci[1])),
        initial_lift=float(initial_lift),
        projected_stable_lift=projected_stable_lift,
        days_to_stable=days_to_stable,
        confidence=confidence,
        recommendation=recommendation,
    )


def summarize_trajectory(trajectory: EffectTrajectory) -> str:
    """Return a one-paragraph plain-English summary for a stakeholder report.

    Args:
        trajectory: Output of analyze_effect_trajectory.

    Returns:
        A narrative paragraph describing the pattern, its meaning, and the
        recommended action.
    """
    p = trajectory.pattern

    if p == "INSUFFICIENT":
        return (
            "The experiment has not yet accumulated enough data to identify a "
            "reliable effect trajectory. At least 7 days of daily lift estimates "
            "are required before pattern analysis is meaningful. Continue running "
            "the experiment and check back once more data has been collected."
        )

    direction = "positive" if trajectory.initial_lift > 0 else "negative"
    lift_pct = f"{abs(trajectory.initial_lift) * 100:.1f}%"
    stable_pct = f"{abs(trajectory.projected_stable_lift) * 100:.1f}%"

    if p == "STABLE":
        return (
            f"The treatment effect has been stable throughout the experiment, "
            f"with an average lift of approximately {lift_pct}. "
            f"No meaningful upward or downward trend was detected "
            f"(slope = {trajectory.slope:.4f}/day, "
            f"95% CI [{trajectory.slope_ci[0]:.4f}, {trajectory.slope_ci[1]:.4f}]). "
            f"This stability suggests the observed effect reflects genuine, "
            f"durable value rather than a transient reaction. "
            f"A shipping decision can be made with confidence based on current results."
        )

    if p == "NOVELTY":
        wait = (
            f" Wait approximately {trajectory.days_to_stable} more days for the "
            f"effect to reach its long-run steady state."
            if trajectory.days_to_stable
            else " Monitor until the decay flattens."
        )
        return (
            f"A novelty effect has been detected. The treatment started with a "
            f"{direction} lift of {lift_pct}, but the effect is declining at "
            f"{abs(trajectory.slope) * 100:.3f} percentage points per day. "
            f"This pattern suggests initial excitement or unfamiliarity rather "
            f"than lasting value. The projected long-run lift is approximately "
            f"{stable_pct}." + wait + " "
            "Avoid making a final shipping decision until the effect stabilises."
        )

    if p == "LEARNING":
        wait = (
            f" Wait approximately {trajectory.days_to_stable} more days for the "
            f"learning curve to plateau."
            if trajectory.days_to_stable
            else " Continue monitoring until growth slows."
        )
        return (
            f"A learning curve has been detected. The treatment effect is growing "
            f"at {abs(trajectory.slope) * 100:.3f} percentage points per day, "
            f"suggesting users are progressively adopting or adapting to the change. "
            f"The current lift of {lift_pct} is likely an underestimate; the "
            f"projected long-run lift is approximately {stable_pct}." + wait + " "
            "Shipping now may undervalue the feature's true impact."
        )

    return ""  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _weighted_linregress(
    x: np.ndarray,
    y: np.ndarray,
    w: np.ndarray,
) -> tuple[float, float, float]:
    """Weighted least-squares regression: y ~ x with weights w.

    Returns:
        (slope, intercept, slope_se)  — slope standard error from weighted MSE.
    """
    w_sum = w.sum()
    x_bar = (w * x).sum() / w_sum
    y_bar = (w * y).sum() / w_sum

    Sxx = (w * (x - x_bar) ** 2).sum()
    Sxy = (w * (x - x_bar) * (y - y_bar)).sum()

    slope = Sxy / Sxx if Sxx > 0 else 0.0
    intercept = y_bar - slope * x_bar

    residuals = y - (slope * x + intercept)
    n = len(x)
    if n > 2 and Sxx > 0:
        mse = (w * residuals**2).sum() / (n - 2)
        slope_se = math.sqrt(mse / Sxx)
    else:
        slope_se = 0.0

    return slope, intercept, slope_se


def _classify_pattern(
    slope: float,
    slope_ci: tuple[float, float],
    initial_lift: float,
    current_mean: float,
    days_running: int,
) -> tuple[Literal["STABLE", "NOVELTY", "LEARNING"], float, int | None]:
    """Return (pattern, projected_stable_lift, days_to_stable)."""
    ci_lo, ci_hi = slope_ci
    ci_overlaps_zero = ci_lo <= 0 <= ci_hi

    # NOVELTY: declining effect with initial positive lift
    if not ci_overlaps_zero and slope < 0 and initial_lift > 0:
        # Project to where lift reaches 10% of its initial value.
        target = 0.1 * initial_lift
        if slope < 0 and initial_lift > target:
            days_needed = math.ceil((target - initial_lift) / slope)
            days_to_stable = max(1, days_needed - days_running)
        else:
            days_to_stable = None
        projected = max(initial_lift + slope * (days_running * 2), 0.0)
        return "NOVELTY", projected, days_to_stable

    # LEARNING: growing effect
    if not ci_overlaps_zero and slope > 0:
        # Project to 2× current experiment length.
        projected = current_mean + slope * days_running
        # days_to_stable: days until slope CI overlaps zero — approximated as
        # remaining days until the trend's extrapolated CI width crosses zero.
        days_to_stable = max(1, days_running)
        return "LEARNING", projected, days_to_stable

    # STABLE: no significant trend (CI overlaps zero, or slope near zero)
    return "STABLE", current_mean, 0


def _compute_confidence(
    n: int,
    slope_ci: tuple[float, float],
) -> Literal["low", "medium", "high"]:
    ci_width = slope_ci[1] - slope_ci[0]
    if n >= 14 and ci_width < 0.005:
        return "high"
    if n >= _MIN_DAYS:
        return "medium"
    return "low"


def _make_recommendation(
    pattern: Literal["STABLE", "NOVELTY", "LEARNING", "INSUFFICIENT"],
    days_to_stable: int | None,
) -> str:
    if pattern == "INSUFFICIENT":
        return "Insufficient data. Run experiment at least 7 days."
    if pattern == "STABLE":
        return "Effect is stable. Safe to make shipping decision."
    if pattern == "NOVELTY":
        n = days_to_stable if days_to_stable and days_to_stable > 0 else None
        if n:
            return f"Novelty effect detected. Wait {n} days for steady-state."
        return "Novelty effect detected. Wait for steady-state."
    if pattern == "LEARNING":
        n = days_to_stable if days_to_stable and days_to_stable > 0 else None
        if n:
            return f"Learning curve detected. Effect improving — wait {n} days."
        return "Learning curve detected. Effect improving — monitor until plateau."
    return ""  # unreachable

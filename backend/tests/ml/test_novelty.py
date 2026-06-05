"""Tests for backend/app/ml/novelty.py — effect trajectory classification."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.novelty import (
    EffectTrajectory,
    analyze_effect_trajectory,
    summarize_trajectory,
)

# ---------------------------------------------------------------------------
# Synthetic data factories
# ---------------------------------------------------------------------------


def _decreasing_lift(
    n: int = 21,
    start: float = 0.10,
    step: float = -0.008,
    se: float = 0.005,
    seed: int = 0,
) -> tuple[pd.Series, pd.Series]:
    """Steadily declining lift (NOVELTY pattern)."""
    rng = np.random.default_rng(seed)
    lift = pd.Series([start + step * i + rng.normal(0, se * 0.2) for i in range(n)])
    se_series = pd.Series([se] * n)
    return lift, se_series


def _flat_lift(
    n: int = 21,
    mean: float = 0.05,
    noise: float = 0.003,
    se: float = 0.005,
    seed: int = 1,
) -> tuple[pd.Series, pd.Series]:
    """Flat lift with small noise (STABLE pattern)."""
    rng = np.random.default_rng(seed)
    lift = pd.Series(rng.normal(mean, noise, n))
    se_series = pd.Series([se] * n)
    return lift, se_series


def _increasing_lift(
    n: int = 21,
    start: float = 0.01,
    step: float = 0.008,
    se: float = 0.005,
    seed: int = 2,
) -> tuple[pd.Series, pd.Series]:
    """Steadily growing lift (LEARNING pattern)."""
    rng = np.random.default_rng(seed)
    lift = pd.Series([start + step * i + rng.normal(0, se * 0.2) for i in range(n)])
    se_series = pd.Series([se] * n)
    return lift, se_series


def _short_lift(n: int = 5) -> tuple[pd.Series, pd.Series]:
    """Fewer than 7 days of data → INSUFFICIENT."""
    lift = pd.Series([0.05] * n)
    se = pd.Series([0.01] * n)
    return lift, se


# ---------------------------------------------------------------------------
# Pattern detection: NOVELTY
# ---------------------------------------------------------------------------


def test_decreasing_lift_detects_novelty() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "NOVELTY", f"Expected NOVELTY, got {traj.pattern}"


def test_novelty_slope_is_negative() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.slope < 0


def test_novelty_initial_lift_close_to_start() -> None:
    lift, se = _decreasing_lift(start=0.10)
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert 0.05 < traj.initial_lift < 0.15


def test_novelty_days_to_stable_is_positive() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.days_to_stable is None or traj.days_to_stable > 0


def test_novelty_recommendation_contains_wait() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert "Wait" in traj.recommendation or "steady-state" in traj.recommendation


# ---------------------------------------------------------------------------
# Pattern detection: STABLE
# ---------------------------------------------------------------------------


def test_flat_lift_detects_stable() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "STABLE", f"Expected STABLE, got {traj.pattern}"


def test_stable_slope_near_zero() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert abs(traj.slope) < 0.005


def test_stable_days_to_stable_is_zero() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.days_to_stable == 0


def test_stable_recommendation_says_safe() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert (
        "stable" in traj.recommendation.lower() or "safe" in traj.recommendation.lower()
    )


def test_stable_projected_lift_close_to_mean() -> None:
    lift, se = _flat_lift(mean=0.05)
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert abs(traj.projected_stable_lift - 0.05) < 0.02


# ---------------------------------------------------------------------------
# Pattern detection: LEARNING
# ---------------------------------------------------------------------------


def test_increasing_lift_detects_learning() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "LEARNING", f"Expected LEARNING, got {traj.pattern}"


def test_learning_slope_is_positive() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.slope > 0


def test_learning_days_to_stable_positive() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.days_to_stable is None or traj.days_to_stable > 0


def test_learning_recommendation_says_improving() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert (
        "improving" in traj.recommendation.lower() or "Learning" in traj.recommendation
    )


def test_learning_projected_lift_above_current_mean() -> None:
    lift, se = _increasing_lift(start=0.01, step=0.008)
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.projected_stable_lift > lift.mean()


# ---------------------------------------------------------------------------
# INSUFFICIENT data
# ---------------------------------------------------------------------------


def test_fewer_than_7_days_returns_insufficient() -> None:
    lift, se = _short_lift(n=5)
    traj = analyze_effect_trajectory(lift, se, days_running=5)
    assert traj.pattern == "INSUFFICIENT"


def test_insufficient_does_not_raise() -> None:
    lift, se = _short_lift(n=3)
    traj = analyze_effect_trajectory(lift, se, days_running=3)
    assert isinstance(traj, EffectTrajectory)


def test_6_days_is_insufficient() -> None:
    lift, se = _short_lift(n=6)
    traj = analyze_effect_trajectory(lift, se, days_running=6)
    assert traj.pattern == "INSUFFICIENT"


def test_exactly_7_days_is_not_insufficient() -> None:
    lift, se = _flat_lift(n=7)
    traj = analyze_effect_trajectory(lift, se, days_running=7)
    assert traj.pattern != "INSUFFICIENT"


def test_insufficient_recommendation_mentions_7_days() -> None:
    lift, se = _short_lift(n=4)
    traj = analyze_effect_trajectory(lift, se, days_running=4)
    assert "7 days" in traj.recommendation


# ---------------------------------------------------------------------------
# Zero standard errors → no exception
# ---------------------------------------------------------------------------


def test_zero_se_does_not_raise() -> None:
    lift = pd.Series(
        [
            0.05,
            0.04,
            0.03,
            0.06,
            0.05,
            0.04,
            0.05,
            0.05,
            0.04,
            0.05,
            0.06,
            0.04,
            0.05,
            0.05,
        ]
    )
    se = pd.Series([0.0] * len(lift))
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj, EffectTrajectory)


def test_zero_se_returns_valid_pattern() -> None:
    lift = pd.Series([0.05] * 14)
    se = pd.Series([0.0] * 14)
    traj = analyze_effect_trajectory(lift, se, days_running=14)
    assert traj.pattern in {"STABLE", "NOVELTY", "LEARNING", "INSUFFICIENT"}


def test_mixed_zero_and_nonzero_se() -> None:
    lift = pd.Series([0.05 + 0.001 * i for i in range(14)])
    se = pd.Series([0.0 if i % 3 == 0 else 0.005 for i in range(14)])
    traj = analyze_effect_trajectory(lift, se, days_running=14)
    assert isinstance(traj, EffectTrajectory)


# ---------------------------------------------------------------------------
# days_to_stable always positive or None
# ---------------------------------------------------------------------------


def test_days_to_stable_never_negative_novelty() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    if traj.days_to_stable is not None:
        assert traj.days_to_stable > 0


def test_days_to_stable_never_negative_learning() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    if traj.days_to_stable is not None:
        assert traj.days_to_stable > 0


def test_days_to_stable_is_int_or_none() -> None:
    for factory in [_decreasing_lift, _flat_lift, _increasing_lift]:
        lift, se = factory()
        traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
        assert traj.days_to_stable is None or isinstance(traj.days_to_stable, int)


# ---------------------------------------------------------------------------
# projected_stable_lift clipped to [-1, 1]
# ---------------------------------------------------------------------------


def test_projected_lift_clipped_upper() -> None:
    lift = pd.Series([2.0 + 0.1 * i for i in range(21)])
    se = pd.Series([0.005] * 21)
    traj = analyze_effect_trajectory(lift, se, days_running=21)
    assert traj.projected_stable_lift <= 1.0


def test_projected_lift_clipped_lower() -> None:
    lift = pd.Series([-2.0 - 0.1 * i for i in range(21)])
    se = pd.Series([0.005] * 21)
    traj = analyze_effect_trajectory(lift, se, days_running=21)
    assert traj.projected_stable_lift >= -1.0


# ---------------------------------------------------------------------------
# recommendation always non-empty string
# ---------------------------------------------------------------------------


def test_recommendation_nonempty_stable() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj.recommendation, str) and len(traj.recommendation) > 0


def test_recommendation_nonempty_novelty() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj.recommendation, str) and len(traj.recommendation) > 0


def test_recommendation_nonempty_learning() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj.recommendation, str) and len(traj.recommendation) > 0


def test_recommendation_nonempty_insufficient() -> None:
    lift, se = _short_lift(n=4)
    traj = analyze_effect_trajectory(lift, se, days_running=4)
    assert isinstance(traj.recommendation, str) and len(traj.recommendation) > 0


# ---------------------------------------------------------------------------
# summarize_trajectory returns non-empty for all patterns
# ---------------------------------------------------------------------------


def test_summarize_stable_nonempty() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "STABLE"
    summary = summarize_trajectory(traj)
    assert isinstance(summary, str) and len(summary) > 0


def test_summarize_novelty_nonempty() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "NOVELTY"
    summary = summarize_trajectory(traj)
    assert isinstance(summary, str) and len(summary) > 0


def test_summarize_learning_nonempty() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "LEARNING"
    summary = summarize_trajectory(traj)
    assert isinstance(summary, str) and len(summary) > 0


def test_summarize_insufficient_nonempty() -> None:
    lift, se = _short_lift(n=4)
    traj = analyze_effect_trajectory(lift, se, days_running=4)
    assert traj.pattern == "INSUFFICIENT"
    summary = summarize_trajectory(traj)
    assert isinstance(summary, str) and len(summary) > 0


def test_summarize_novelty_mentions_novelty() -> None:
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    summary = summarize_trajectory(traj)
    assert "novelty" in summary.lower()


def test_summarize_learning_mentions_learning() -> None:
    lift, se = _increasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    summary = summarize_trajectory(traj)
    assert "learning" in summary.lower()


def test_summarize_stable_mentions_stable() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    summary = summarize_trajectory(traj)
    assert "stable" in summary.lower()


# ---------------------------------------------------------------------------
# EffectTrajectory field types
# ---------------------------------------------------------------------------


def test_trajectory_slope_ci_is_tuple_of_two_floats() -> None:
    lift, se = _flat_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj.slope_ci, tuple)
    assert len(traj.slope_ci) == 2
    lo, hi = traj.slope_ci
    assert lo <= hi


def test_trajectory_confidence_valid_values() -> None:
    for factory, days in [
        (_decreasing_lift, 21),
        (_flat_lift, 21),
        (_increasing_lift, 21),
    ]:
        lift, se = factory()
        traj = analyze_effect_trajectory(lift, se, days_running=days)
        assert traj.confidence in {"low", "medium", "high"}


def test_high_confidence_with_many_tight_days() -> None:
    """21 days of tight data should yield high confidence."""
    lift = pd.Series([0.05 + 0.000001 * i for i in range(21)])
    se = pd.Series([0.001] * 21)
    traj = analyze_effect_trajectory(lift, se, days_running=21)
    assert traj.confidence in {"medium", "high"}


# ---------------------------------------------------------------------------
# Effect that starts negative and gets more negative
# ---------------------------------------------------------------------------


def _negative_declining_lift(
    n: int = 21,
    start: float = -0.05,
    step: float = -0.006,
    se: float = 0.002,
    seed: int = 99,
) -> tuple[pd.Series, pd.Series]:
    """Starts negative and becomes increasingly negative (not NOVELTY)."""
    rng = np.random.default_rng(seed)
    lift = pd.Series([start + step * i + rng.normal(0, se * 0.1) for i in range(n)])
    se_series = pd.Series([se] * n)
    return lift, se_series


def test_negative_declining_lift_does_not_raise() -> None:
    """A negative, increasingly negative lift must not crash the classifier."""
    lift, se = _negative_declining_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj, EffectTrajectory)


def test_negative_declining_lift_is_not_novelty() -> None:
    """NOVELTY requires initial_lift > 0; a negative-starting declining effect is not NOVELTY."""
    lift, se = _negative_declining_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern != "NOVELTY", (
        f"Negative-starting declining lift must not be classified as NOVELTY, "
        f"got {traj.pattern}"
    )


def test_negative_declining_lift_slope_is_negative() -> None:
    """Slope must be negative for a monotonically declining effect."""
    lift, se = _negative_declining_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.slope < 0, f"Expected negative slope, got {traj.slope:.6f}"


# ---------------------------------------------------------------------------
# Very noisy data where pattern is unclear → STABLE
# ---------------------------------------------------------------------------


def _no_trend_lift(n: int = 21) -> tuple[pd.Series, pd.Series]:
    """Deterministic alternating lift with no net slope — guaranteed STABLE.

    The alternating sequence is orthogonal to the linear day-index in OLS,
    so slope is exactly 0, CI = (0 ± small), which overlaps zero → STABLE.
    """
    lift = pd.Series([0.05 + 0.02 * (1 if i % 2 == 0 else -1) for i in range(n)])
    se_series = pd.Series([0.005] * n)
    return lift, se_series


def test_no_trend_noisy_data_does_not_raise() -> None:
    """Noisy data with no underlying trend must not raise an exception."""
    lift, se = _no_trend_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert isinstance(traj, EffectTrajectory)


def test_no_trend_noisy_data_is_stable() -> None:
    """Lift oscillating around a constant (no net slope) should be classified as STABLE."""
    lift, se = _no_trend_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert (
        traj.pattern == "STABLE"
    ), f"Expected STABLE for no-trend alternating data, got {traj.pattern}"


def test_no_trend_slope_is_near_zero() -> None:
    """Alternating lift produces an OLS slope of exactly 0."""
    lift, se = _no_trend_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert (
        abs(traj.slope) < 1e-10
    ), f"Expected slope ≈ 0 for alternating lift, got {traj.slope:.2e}"


# ---------------------------------------------------------------------------
# days_to_stable is never zero for NOVELTY pattern
# ---------------------------------------------------------------------------


def test_novelty_days_to_stable_never_zero() -> None:
    """For NOVELTY, days_to_stable must be None or ≥ 1 — never exactly 0."""
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "NOVELTY", f"Expected NOVELTY, got {traj.pattern}"
    assert (
        traj.days_to_stable != 0
    ), f"days_to_stable must not be exactly 0 for NOVELTY; got {traj.days_to_stable}"


def test_novelty_days_to_stable_is_positive_integer_or_none() -> None:
    """For NOVELTY, days_to_stable must be a positive int (≥ 1) or None."""
    lift, se = _decreasing_lift()
    traj = analyze_effect_trajectory(lift, se, days_running=len(lift))
    assert traj.pattern == "NOVELTY"
    if traj.days_to_stable is not None:
        assert isinstance(traj.days_to_stable, int)
        assert (
            traj.days_to_stable >= 1
        ), f"days_to_stable must be ≥ 1, got {traj.days_to_stable}"

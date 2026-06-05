"""Tests for backend/app/stats/cuped.py.

Expected values verified ahead of writing:
  - perfect_linear_data: θ = 2.0 exactly; adj control = [6]*5, adj treatment = [7]*5
  - high_corr (seed=42, n=500, balanced): r ≈ 0.909, empirical reduction ≈ 82.7%
  - zero_corr (seed=42, n=500, balanced): r ≈ -0.01, reduction ≈ 0.01%
"""

from __future__ import annotations

import numpy as np
import pytest

from app.stats.cuped import (
    CUPEDGroupSummary,
    CUPEDResult,
    apply_cuped,
    estimate_variance_reduction,
    recommend_cuped,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rng() -> np.random.Generator:
    return np.random.default_rng(42)


@pytest.fixture()
def high_corr_data(rng: np.random.Generator):
    """500 users, balanced assignment, pre/post correlation ≈ 0.909.

    post = 0.9 * pre + treatment_effect * 5 + Normal(0, 3).
    Perfectly balanced (alternating assignment) so CUPED mean-adjustment ≈ 0.
    """
    n = 500
    pre = rng.normal(50, 10, n)
    assignment = np.tile([0, 1], n // 2)
    post = 0.9 * pre + assignment * 5 + rng.normal(0, 3, n)
    return pre.tolist(), post.tolist(), assignment.tolist()


@pytest.fixture()
def zero_corr_data(rng: np.random.Generator):
    """500 users; post is drawn independently of pre — correlation ≈ 0."""
    n = 500
    pre = rng.normal(50, 10, n)
    assignment = np.tile([0, 1], n // 2)
    post = rng.normal(100, 20, n) + assignment * 5
    return pre.tolist(), post.tolist(), assignment.tolist()


@pytest.fixture()
def perfect_linear_data():
    """post = 2*pre + group_effect.  θ should be exactly 2.0.

    control   pre=[1..5], post=[2,4,6,8,10]   → adj=[6,6,6,6,6]
    treatment pre=[1..5], post=[3,5,7,9,11]   → adj=[7,7,7,7,7]
    """
    pre = [1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    post = [2.0, 4.0, 6.0, 8.0, 10.0, 3.0, 5.0, 7.0, 9.0, 11.0]
    assignment = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
    return pre, post, assignment


# ---------------------------------------------------------------------------
# apply_cuped — core behaviour
# ---------------------------------------------------------------------------


class TestApplyCuped:
    def test_returns_cuped_result_model(self, high_corr_data) -> None:
        pre, post, assign = high_corr_data
        assert isinstance(apply_cuped(pre, post, assign), CUPEDResult)

    def test_theta_exact_for_perfect_linear_data(self, perfect_linear_data) -> None:
        """θ = Cov(x,y)/Var(x) should be exactly 2.0 for post = 2*pre + constant."""
        pre, post, assign = perfect_linear_data
        result = apply_cuped(pre, post, assign)
        assert result.theta == pytest.approx(2.0, abs=1e-9)

    def test_adjusted_means_correct_for_perfect_linear_data(
        self, perfect_linear_data
    ) -> None:
        """With θ=2, all control adj = 6.0 and all treatment adj = 7.0."""
        pre, post, assign = perfect_linear_data
        result = apply_cuped(pre, post, assign)
        assert result.control_summary.adjusted_mean == pytest.approx(6.0, abs=1e-9)
        assert result.treatment_summary.adjusted_mean == pytest.approx(7.0, abs=1e-9)

    def test_post_means_correct_for_perfect_linear_data(
        self, perfect_linear_data
    ) -> None:
        pre, post, assign = perfect_linear_data
        result = apply_cuped(pre, post, assign)
        assert result.control_summary.post_mean == pytest.approx(6.0, abs=1e-9)
        assert result.treatment_summary.post_mean == pytest.approx(7.0, abs=1e-9)

    def test_group_n_users_sum_to_total(self, high_corr_data) -> None:
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert result.control_summary.n_users + result.treatment_summary.n_users == len(
            pre
        )

    def test_group_names_are_correct(self, high_corr_data) -> None:
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert result.control_summary.group_name == "control"
        assert result.treatment_summary.group_name == "treatment"

    def test_high_correlation_produces_meaningful_variance_reduction(
        self, high_corr_data
    ) -> None:
        """With r ≈ 0.909, empirical variance reduction should exceed 70%."""
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert result.variance_reduction_pct > 70

    def test_zero_correlation_produces_near_zero_variance_reduction(
        self, zero_corr_data
    ) -> None:
        """With r ≈ 0.01, variance reduction should be negligible (< 5%)."""
        pre, post, assign = zero_corr_data
        result = apply_cuped(pre, post, assign)
        assert result.variance_reduction_pct < 5.0

    def test_adjusted_ci_narrower_than_unadjusted_when_high_corr(
        self, high_corr_data
    ) -> None:
        """CUPED should shrink the confidence interval when ρ is high."""
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        adj_lo, adj_hi = result.adjusted_test_result.confidence_interval
        raw_lo, raw_hi = result.unadjusted_test_result.confidence_interval
        assert (adj_hi - adj_lo) < (raw_hi - raw_lo)

    def test_adjusted_and_unadjusted_lifts_nearly_equal_when_zero_corr(
        self, zero_corr_data
    ) -> None:
        """With θ ≈ 0, the adjustment changes the lift by < 0.5 units."""
        pre, post, assign = zero_corr_data
        result = apply_cuped(pre, post, assign)
        diff = abs(
            result.adjusted_test_result.lift_abs
            - result.unadjusted_test_result.lift_abs
        )
        assert diff < 0.5

    def test_constant_covariate_returns_theta_zero_and_no_reduction(self) -> None:
        """Var(X) = 0 — CUPED cannot adjust; should not crash."""
        pre = [5.0] * 20 + [5.0] * 20
        post = [10.0] * 20 + [12.0] * 20
        assign = [0] * 20 + [1] * 20
        result = apply_cuped(pre, post, assign)
        assert result.theta == 0.0
        assert result.variance_reduction_pct == 0.0

    def test_constant_covariate_recommendation_says_unlikely(self) -> None:
        pre = [5.0] * 20 + [5.0] * 20
        post = [10.0] * 20 + [12.0] * 20
        assign = [0] * 20 + [1] * 20
        result = apply_cuped(pre, post, assign)
        assert "unlikely" in result.recommendation.lower()

    def test_correlation_is_in_valid_range(self, high_corr_data) -> None:
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert -1.0 <= result.correlation_pre_post <= 1.0

    def test_high_corr_correlation_is_high(self, high_corr_data) -> None:
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert result.correlation_pre_post > 0.7

    def test_recommendation_string_is_non_empty(self, high_corr_data) -> None:
        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0

    def test_variance_reduction_is_non_negative(self, zero_corr_data) -> None:
        pre, post, assign = zero_corr_data
        result = apply_cuped(pre, post, assign)
        assert result.variance_reduction_pct >= 0.0

    def test_both_test_results_are_test_result_instances(self, high_corr_data) -> None:
        from app.stats.testing import TestResult

        pre, post, assign = high_corr_data
        result = apply_cuped(pre, post, assign)
        assert isinstance(result.adjusted_test_result, TestResult)
        assert isinstance(result.unadjusted_test_result, TestResult)


# ---------------------------------------------------------------------------
# apply_cuped — input validation
# ---------------------------------------------------------------------------


class TestApplyCupedValidation:
    def test_mismatched_pre_post_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            apply_cuped([1.0, 2.0], [1.5, 2.5, 3.0], [0, 1, 0])

    def test_mismatched_assignment_length_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            apply_cuped([1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [0, 1])

    def test_invalid_assignment_value_raises(self) -> None:
        with pytest.raises(ValueError, match="0 or 1"):
            apply_cuped([1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [0, 2, 1])

    def test_negative_assignment_value_raises(self) -> None:
        with pytest.raises(ValueError, match="0 or 1"):
            apply_cuped([1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [0, -1, 1])

    def test_no_control_users_raises(self) -> None:
        with pytest.raises(ValueError, match="control"):
            apply_cuped([1.0, 2.0], [1.5, 2.5], [1, 1])

    def test_no_treatment_users_raises(self) -> None:
        with pytest.raises(ValueError, match="treatment"):
            apply_cuped([1.0, 2.0], [1.5, 2.5], [0, 0])

    def test_nan_in_pre_raises(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            apply_cuped([1.0, float("nan"), 3.0], [1.5, 2.5, 3.5], [0, 0, 1])

    def test_nan_in_post_raises(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            apply_cuped([1.0, 2.0, 3.0], [1.5, float("nan"), 3.5], [0, 0, 1])

    def test_inf_in_pre_raises(self) -> None:
        with pytest.raises(ValueError, match="Inf"):
            apply_cuped([1.0, float("inf"), 3.0], [1.5, 2.5, 3.5], [0, 0, 1])

    def test_inf_in_post_raises(self) -> None:
        with pytest.raises(ValueError, match="Inf"):
            apply_cuped([1.0, 2.0, 3.0], [1.5, float("inf"), 3.5], [0, 0, 1])

    def test_empty_arrays_raise(self) -> None:
        with pytest.raises(ValueError):
            apply_cuped([], [], [])

    def test_single_user_per_group_accepted(self) -> None:
        """Two users (one per group) is technically valid — warnings expected."""
        result = apply_cuped([1.0, 2.0], [1.5, 2.5], [0, 1])
        assert isinstance(result, CUPEDResult)


# ---------------------------------------------------------------------------
# estimate_variance_reduction
# ---------------------------------------------------------------------------


class TestEstimateVarianceReduction:
    def test_high_correlation_gives_large_reduction(self, rng) -> None:
        """post ≈ 0.9 * pre → r ≈ 0.91, reduction ≈ 83%."""
        x = rng.normal(50, 10, 1000)
        y = 0.9 * x + rng.normal(0, 3, 1000)
        reduction = estimate_variance_reduction(x.tolist(), y.tolist())
        assert reduction > 70.0

    def test_zero_correlation_gives_near_zero_reduction(self, rng) -> None:
        x = rng.normal(50, 10, 1000)
        y = rng.normal(100, 20, 1000)  # independent
        reduction = estimate_variance_reduction(x.tolist(), y.tolist())
        assert reduction < 5.0

    def test_perfect_positive_correlation_gives_100pct(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]  # y = 2x exactly
        reduction = estimate_variance_reduction(x, y)
        assert reduction == pytest.approx(100.0, abs=1e-6)

    def test_perfect_negative_correlation_gives_100pct(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [-1.0, -2.0, -3.0, -4.0, -5.0]  # y = -x
        reduction = estimate_variance_reduction(x, y)
        assert reduction == pytest.approx(100.0, abs=1e-6)

    def test_constant_pre_gives_zero_reduction(self) -> None:
        """Var(X) = 0 → correlation undefined → reduction = 0."""
        x = [5.0, 5.0, 5.0, 5.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert estimate_variance_reduction(x, y) == 0.0

    def test_reduction_is_always_non_negative(self, rng) -> None:
        """Numerical noise should not produce negative reduction."""
        x = rng.normal(0, 1, 100)
        y = rng.normal(0, 1, 100)
        assert estimate_variance_reduction(x.tolist(), y.tolist()) >= 0.0

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            estimate_variance_reduction([1.0, 2.0], [1.5, 2.5, 3.0])

    def test_nan_raises(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            estimate_variance_reduction([1.0, float("nan")], [1.0, 2.0])

    def test_reduction_is_percentage(self, rng) -> None:
        """Return value should be in [0, 100], not [0, 1]."""
        x = rng.normal(0, 1, 200)
        y = 0.5 * x + rng.normal(0, 1, 200)
        reduction = estimate_variance_reduction(x.tolist(), y.tolist())
        assert 0.0 <= reduction <= 100.0


# ---------------------------------------------------------------------------
# recommend_cuped
# ---------------------------------------------------------------------------


class TestRecommendCuped:
    def test_zero_correlation_says_unlikely(self) -> None:
        assert "unlikely" in recommend_cuped(0.0).lower()

    def test_low_correlation_says_unlikely(self) -> None:
        assert "unlikely" in recommend_cuped(0.05).lower()

    def test_boundary_low_to_modest(self) -> None:
        """r = 0.1 crosses into the 'modest' tier."""
        result = recommend_cuped(0.1)
        assert "unlikely" not in result.lower()
        assert "modest" in result.lower()

    def test_medium_correlation_says_modest(self) -> None:
        assert "modest" in recommend_cuped(0.2).lower()

    def test_good_correlation_says_good_or_candidate(self) -> None:
        result = recommend_cuped(0.4)
        assert "good" in result.lower() or "candidate" in result.lower()

    def test_high_correlation_says_strongly(self) -> None:
        assert "strongly" in recommend_cuped(0.7).lower()

    def test_very_high_correlation_says_strongly(self) -> None:
        assert "strongly" in recommend_cuped(0.95).lower()

    def test_negative_correlation_equals_positive(self) -> None:
        """CUPED uses |r|; sign does not affect recommendation."""
        assert recommend_cuped(-0.7) == recommend_cuped(0.7)
        assert recommend_cuped(-0.2) == recommend_cuped(0.2)

    def test_variance_reduction_percentage_appears_in_string(self) -> None:
        """r = 0.5 → r² = 25%; the string should mention '25'."""
        assert "25" in recommend_cuped(0.5)

    def test_returns_non_empty_string(self) -> None:
        assert isinstance(recommend_cuped(0.3), str)
        assert len(recommend_cuped(0.3)) > 0

    def test_boundary_good_to_strongly(self) -> None:
        """r = 0.5 is the threshold between 'good candidate' and 'strongly'."""
        below = recommend_cuped(0.499)
        above = recommend_cuped(0.5)
        assert "strongly" not in below.lower()
        assert "strongly" in above.lower()

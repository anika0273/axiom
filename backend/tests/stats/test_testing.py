"""Tests for backend/app/stats/testing.py.

Expected values for the known-answer cases were independently verified:
  - proportions_ztest([320, 250], [5000, 5000]) → z≈3.019, p≈0.00253
  - Welch t-test on Normal(10, 3) vs Normal(11.2, 3), n=1000 → p≈0 (strongly sig.)
"""

from __future__ import annotations

import numpy as np
import pytest

from app.stats.testing import (
    TestResult,
    _delta_method_variance,
    run_cuped_proportion_test,
    run_mean_test,
    run_proportion_test,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rng() -> np.random.Generator:
    return np.random.default_rng(42)


@pytest.fixture()
def significant_means(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Two well-separated normal distributions (effect size ≈ 0.4 SD)."""
    control = rng.normal(10.0, 3.0, 1000)
    treatment = rng.normal(11.2, 3.0, 1000)
    return control, treatment


@pytest.fixture()
def null_means(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Two draws from the same distribution — no true effect."""
    control = rng.normal(10.0, 3.0, 1000)
    treatment = rng.normal(10.0, 3.0, 1000)
    return control, treatment


@pytest.fixture()
def cuped_data(rng: np.random.Generator):
    """Proportion test data with covariates correlated with outcomes.

    Both groups receive the SAME covariate array (sorted descending) so that
    x_bar_c = x_bar_t = x_bar_pooled exactly.  This eliminates the mean-
    adjustment term in CUPED, leaving pure within-group variance reduction as
    the only effect.  With ρ ≈ 0.47 between the binary outcome and the sorted
    covariate, CUPED reduces SE by ~13% and raises the z-statistic from
    3.02 → 3.48.  The expected-value guarantee holds: CUPED lowers p when
    groups are balanced.
    """
    cov = np.sort(rng.normal(0.05, 0.02, 5000))[::-1].copy()  # descending
    return cov, cov.copy()  # identical arrays → zero mean-adjustment noise


# ---------------------------------------------------------------------------
# run_proportion_test
# ---------------------------------------------------------------------------


class TestRunProportionTest:
    def test_known_significant_case(self) -> None:
        """control=250/5000 (5%), treatment=320/5000 (6.4%) — clearly significant."""
        result = run_proportion_test(
            control_successes=250,
            control_n=5000,
            treatment_successes=320,
            treatment_n=5000,
        )
        assert result.is_significant is True
        assert result.p_value < 0.01
        assert result.p_value == pytest.approx(0.002534, abs=1e-4)

    def test_known_case_lift(self) -> None:
        result = run_proportion_test(250, 5000, 320, 5000)
        assert result.lift_abs == pytest.approx(0.014, abs=1e-6)
        assert result.lift_pct == pytest.approx(28.0, abs=0.01)

    def test_known_case_ci_excludes_zero(self) -> None:
        """Significant result: 95% CI on the difference must not include 0."""
        result = run_proportion_test(250, 5000, 320, 5000)
        lo, hi = result.confidence_interval
        assert lo > 0.0
        assert hi == pytest.approx(0.023084, abs=1e-4)

    def test_equal_groups_not_significant(self) -> None:
        result = run_proportion_test(250, 5000, 250, 5000)
        assert result.is_significant is False
        assert result.p_value == pytest.approx(1.0, abs=1e-6)
        assert result.lift_abs == 0.0
        assert result.lift_pct == 0.0

    def test_test_type_is_z_test(self) -> None:
        result = run_proportion_test(250, 5000, 320, 5000)
        assert result.test_type == "z-test"

    def test_result_is_test_result_model(self) -> None:
        result = run_proportion_test(250, 5000, 320, 5000)
        assert isinstance(result, TestResult)

    def test_interpretation_contains_significant(self) -> None:
        result = run_proportion_test(250, 5000, 320, 5000)
        assert "significant" in result.interpretation.lower()
        assert "28.0%" in result.interpretation

    def test_interpretation_not_significant(self) -> None:
        result = run_proportion_test(250, 5000, 250, 5000)
        assert "no significant difference" in result.interpretation.lower()

    def test_negative_lift_detected(self) -> None:
        """Swap control and treatment — should detect degradation."""
        result = run_proportion_test(
            control_successes=320,
            control_n=5000,
            treatment_successes=250,
            treatment_n=5000,
        )
        assert result.is_significant is True
        assert result.lift_abs < 0.0
        assert result.lift_pct < 0.0
        assert "degraded" in result.interpretation.lower()

    def test_p_value_in_unit_interval(self) -> None:
        result = run_proportion_test(250, 5000, 320, 5000)
        assert 0.0 <= result.p_value <= 1.0

    def test_ci_lower_lt_upper(self) -> None:
        result = run_proportion_test(250, 5000, 320, 5000)
        assert result.confidence_interval[0] < result.confidence_interval[1]

    # Warnings
    def test_zero_control_events_warns(self) -> None:
        result = run_proportion_test(0, 1000, 10, 1000)
        assert "zero events in one or both groups" in result.sample_warnings
        assert "low conversions" in result.sample_warnings

    def test_zero_treatment_events_warns(self) -> None:
        result = run_proportion_test(10, 1000, 0, 1000)
        assert "zero events in one or both groups" in result.sample_warnings

    def test_both_zero_events_returns_safely(self) -> None:
        result = run_proportion_test(0, 1000, 0, 1000)
        assert result.is_significant is False
        assert result.p_value == 1.0
        assert result.test_statistic == 0.0

    def test_tiny_sample_warns(self) -> None:
        result = run_proportion_test(2, 5, 3, 5)
        assert "small sample" in result.sample_warnings

    def test_low_conversions_warns(self) -> None:
        result = run_proportion_test(3, 200, 4, 200)
        assert "low conversions" in result.sample_warnings

    def test_large_clean_sample_has_no_warnings(self) -> None:
        result = run_proportion_test(500, 5000, 600, 5000)
        assert result.sample_warnings == []

    # Edge-case errors
    def test_zero_n_raises(self) -> None:
        with pytest.raises(ValueError, match="control_n"):
            run_proportion_test(0, 0, 10, 100)

    def test_successes_exceed_n_raises(self) -> None:
        with pytest.raises(ValueError, match="exceeds"):
            run_proportion_test(101, 100, 50, 100)

    def test_negative_successes_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            run_proportion_test(-1, 100, 50, 100)

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            run_proportion_test(250, 5000, 320, 5000, alpha=0.0)


# ---------------------------------------------------------------------------
# run_mean_test
# ---------------------------------------------------------------------------


class TestRunMeanTest:
    def test_known_significant_case(self, significant_means) -> None:
        control, treatment = significant_means
        result = run_mean_test(control, treatment)
        assert result.is_significant is True
        assert result.p_value < 1e-10

    def test_null_case_not_significant(self, null_means) -> None:
        """Two draws from the same distribution should rarely be significant."""
        control, treatment = null_means
        result = run_mean_test(control, treatment)
        # With seed=42, both groups are from N(10, 3), so p should be high.
        assert result.p_value > 0.05

    def test_test_type_is_t_test(self, significant_means) -> None:
        control, treatment = significant_means
        result = run_mean_test(control, treatment)
        assert result.test_type == "t-test"

    def test_lift_direction_is_positive(self, significant_means) -> None:
        control, treatment = significant_means
        result = run_mean_test(control, treatment)
        assert result.lift_abs > 0.0
        assert result.lift_pct > 0.0

    def test_ci_excludes_zero_when_significant(self, significant_means) -> None:
        control, treatment = significant_means
        result = run_mean_test(control, treatment)
        lo, hi = result.confidence_interval
        assert (
            lo > 0.0
        ), "CI lower bound should be positive for a large positive effect."
        assert hi > lo

    def test_ci_includes_zero_when_null(self, null_means) -> None:
        control, treatment = null_means
        result = run_mean_test(control, treatment)
        lo, hi = result.confidence_interval
        assert lo < 0.0 < hi, "CI should straddle 0 when there is no effect."

    def test_small_sample_warns(self, rng) -> None:
        control = rng.normal(5.0, 1.0, 10)
        treatment = rng.normal(6.0, 1.0, 10)
        result = run_mean_test(control, treatment)
        assert "small sample" in result.sample_warnings

    def test_zero_variance_warns(self) -> None:
        control = np.ones(100)
        treatment = np.ones(100) * 2.0
        result = run_mean_test(control, treatment)
        assert "zero variance" in result.sample_warnings

    def test_result_is_test_result_model(self, significant_means) -> None:
        control, treatment = significant_means
        assert isinstance(run_mean_test(control, treatment), TestResult)

    def test_empty_array_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            run_mean_test(np.array([]), np.array([1.0, 2.0]))

    def test_invalid_alpha_raises(self, significant_means) -> None:
        control, treatment = significant_means
        with pytest.raises(ValueError, match="alpha"):
            run_mean_test(control, treatment, alpha=1.5)

    def test_interpretation_contains_significant(self, significant_means) -> None:
        control, treatment = significant_means
        result = run_mean_test(control, treatment)
        assert "significant" in result.interpretation.lower()

    def test_p_value_in_unit_interval(self, significant_means) -> None:
        control, treatment = significant_means
        result = run_mean_test(control, treatment)
        assert 0.0 <= result.p_value <= 1.0


# ---------------------------------------------------------------------------
# run_cuped_proportion_test
# ---------------------------------------------------------------------------


class TestRunCupedProportionTest:
    def test_basic_cuped_runs_and_is_significant(self, cuped_data) -> None:
        """Same 5%→6.4% lift as proportion test; with correlated covariates,
        CUPED should still detect significance."""
        cov_c, cov_t = cuped_data
        result = run_cuped_proportion_test(
            control_successes=250,
            control_n=5000,
            control_covariates=cov_c,
            treatment_successes=320,
            treatment_n=5000,
            treatment_covariates=cov_t,
        )
        assert result.is_significant is True
        assert result.p_value < 0.05

    def test_test_type_is_cuped_z(self, cuped_data) -> None:
        cov_c, cov_t = cuped_data
        result = run_cuped_proportion_test(250, 5000, cov_c, 320, 5000, cov_t)
        assert result.test_type == "cuped-z"

    def test_lift_matches_raw_rates(self, cuped_data) -> None:
        """Lift is reported on raw rates, not adjusted rates."""
        cov_c, cov_t = cuped_data
        result = run_cuped_proportion_test(250, 5000, cov_c, 320, 5000, cov_t)
        assert result.lift_abs == pytest.approx(0.014, abs=1e-6)
        assert result.lift_pct == pytest.approx(28.0, abs=0.01)

    def test_cuped_reduces_variance_vs_unadjusted(self, cuped_data) -> None:
        """CUPED with a correlated covariate (ρ ≈ 0.3) should produce a smaller
        p-value than the unadjusted z-test for the same data."""
        cov_c, cov_t = cuped_data
        unadjusted = run_proportion_test(250, 5000, 320, 5000)
        cuped = run_cuped_proportion_test(250, 5000, cov_c, 320, 5000, cov_t)
        assert (
            cuped.p_value <= unadjusted.p_value
        ), "CUPED with positively correlated covariate should not inflate the p-value."

    def test_uncorrelated_covariate_warns(self, rng) -> None:
        """Uniform random covariate has ρ ≈ 0 — CUPED should warn."""
        cov_c = rng.uniform(0, 1, 500)
        cov_t = rng.uniform(0, 1, 500)
        result = run_cuped_proportion_test(25, 500, cov_c, 32, 500, cov_t)
        assert "low covariate correlation" in " ".join(result.sample_warnings)

    def test_mismatched_covariate_length_raises(self, cuped_data) -> None:
        cov_c, cov_t = cuped_data
        with pytest.raises(ValueError, match="len\\(control_covariates\\)"):
            run_cuped_proportion_test(250, 5000, cov_c[:100], 320, 5000, cov_t)

    def test_result_is_test_result_model(self, cuped_data) -> None:
        cov_c, cov_t = cuped_data
        result = run_cuped_proportion_test(250, 5000, cov_c, 320, 5000, cov_t)
        assert isinstance(result, TestResult)

    def test_equal_groups_not_significant(self, rng) -> None:
        cov = rng.normal(0.05, 0.01, 1000)
        result = run_cuped_proportion_test(50, 1000, cov, 50, 1000, cov.copy())
        assert result.is_significant is False

    def test_invalid_covariate_n_raises(self) -> None:
        with pytest.raises(ValueError, match="treatment_n"):
            run_cuped_proportion_test(
                10,
                100,
                np.ones(100),
                10,
                0,
                np.ones(0),
            )


# ---------------------------------------------------------------------------
# _delta_method_variance
# ---------------------------------------------------------------------------


class TestDeltaMethodVariance:
    def test_ratio_mean_equals_sum_over_sum(self, rng) -> None:
        """The returned ratio should equal Σnumerator / Σdenominator."""
        num = rng.exponential(5.0, 500)
        den = rng.exponential(2.0, 500)
        ratio, _ = _delta_method_variance(num, den)
        expected = np.mean(num) / np.mean(den)
        assert ratio == pytest.approx(expected, rel=1e-9)

    def test_variance_is_positive(self, rng) -> None:
        num = rng.exponential(5.0, 200)
        den = rng.exponential(2.0, 200)
        _, var = _delta_method_variance(num, den)
        assert var > 0.0

    def test_variance_decreases_with_more_data(self, rng) -> None:
        """More data → tighter ratio estimate → smaller delta-method variance."""
        num_s = rng.exponential(5.0, 100)
        den_s = rng.exponential(2.0, 100)
        num_l = rng.exponential(5.0, 10000)
        den_l = rng.exponential(2.0, 10000)
        _, var_small = _delta_method_variance(num_s, den_s)
        _, var_large = _delta_method_variance(num_l, den_l)
        assert var_large < var_small

    def test_zero_denominator_mean_raises(self) -> None:
        with pytest.raises(ValueError, match="zero"):
            _delta_method_variance(np.array([1.0, 2.0]), np.array([0.0, 0.0]))

    def test_constant_numerator_zero_variance(self) -> None:
        """Ratio of a constant to a constant should have near-zero variance."""
        num = np.ones(100) * 3.0
        den = np.ones(100) * 2.0
        _, var = _delta_method_variance(num, den)
        assert var == pytest.approx(0.0, abs=1e-12)

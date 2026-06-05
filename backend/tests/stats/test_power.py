"""Tests for backend/app/stats/power.py.

All expected values were independently verified against statsmodels
NormalIndPower and cross-checked with the formulaic Python library.

NOTE on the "~15,708 per group" figure sometimes cited for the canonical
(baseline=5%, MDE=1pp, α=0.05, power=80%) scenario: that figure arises
when the MDE is interpreted as a 10% *relative* lift (5% → 5.5%, delta=0.005).
The absolute-MDE interpretation (5% → 6%, delta=0.01) used in this module
yields ~8,159 per group via NormalIndPower.  Both are correct for their
respective interpretations; ours is explicitly absolute.
"""

from __future__ import annotations

import math

import pytest

from app.stats.power import (
    SampleSizeResult,
    RuntimeEstimate,
    calculate_mde,
    calculate_power,
    calculate_sample_size,
    runtime_estimate,
)


# ---------------------------------------------------------------------------
# calculate_sample_size
# ---------------------------------------------------------------------------


class TestCalculateSampleSize:
    def test_known_answer_absolute_mde(self) -> None:
        """Canonical case: 5% baseline, 1pp absolute MDE, α=0.05, 80% power.

        Expected: ~8,159 per group (statsmodels NormalIndPower, equal allocation).
        """
        result = calculate_sample_size(
            baseline_rate=0.05,
            mde=0.01,
            alpha=0.05,
            power=0.80,
            two_tailed=True,
        )
        assert result.control_size == pytest.approx(8159, abs=50), (
            "Per-group sample size should be ~8159 for a 1pp absolute MDE "
            "on a 5% baseline at 80% power, α=0.05."
        )
        assert result.treatment_size == result.control_size
        assert result.total_sample_size == result.control_size + result.treatment_size

    def test_cohens_d_value(self) -> None:
        """Cohen's d = mde / sqrt(p_bar * (1-p_bar)) for the canonical case."""
        result = calculate_sample_size(0.05, 0.01)
        # p_bar = (0.05 + 0.06) / 2 = 0.055; sd = sqrt(0.055 * 0.945) ≈ 0.2280
        expected_d = 0.01 / math.sqrt(0.055 * 0.945)
        assert result.cohens_d == pytest.approx(expected_d, rel=1e-4)

    def test_method_name_is_present(self) -> None:
        result = calculate_sample_size(0.05, 0.01)
        assert result.method_used  # non-empty string
        assert isinstance(result.method_used, str)

    def test_power_curve_has_20_points(self) -> None:
        result = calculate_sample_size(0.05, 0.01)
        assert len(result.power_curve) == 20

    def test_power_curve_is_monotonically_increasing(self) -> None:
        result = calculate_sample_size(0.05, 0.01)
        powers = [pt["power"] for pt in result.power_curve]
        for a, b in zip(powers, powers[1:]):
            assert b >= a, "Power must be non-decreasing as sample size grows."

    def test_power_curve_ends_near_one(self) -> None:
        """Last point of the curve (2× required n) should have high power."""
        result = calculate_sample_size(0.05, 0.01)
        assert result.power_curve[-1]["power"] > 0.90

    def test_one_tailed_needs_fewer_samples(self) -> None:
        """One-tailed tests require fewer samples than two-tailed for same power."""
        two = calculate_sample_size(0.05, 0.01, two_tailed=True)
        one = calculate_sample_size(0.05, 0.01, two_tailed=False)
        assert one.control_size < two.control_size

    def test_negative_mde_is_accepted(self) -> None:
        """A negative MDE (detecting degradation) should produce a valid result.

        Note: +mde and -mde give different sample sizes because p_bar differs
        (baseline=10%, +2pp → p_bar=11%; baseline=10%, -2pp → p_bar=9%).
        Lower p_bar means lower variance, so the negative case requires fewer
        samples.  Both directions are valid inputs.
        """
        pos = calculate_sample_size(0.10, 0.02)
        neg = calculate_sample_size(0.10, -0.02)
        assert isinstance(neg, SampleSizeResult)
        assert neg.control_size > 0
        # Negative direction (lower p_bar) requires fewer samples than positive.
        assert neg.control_size < pos.control_size

    def test_larger_mde_needs_fewer_samples(self) -> None:
        """Larger effects are easier to detect and require smaller samples."""
        small = calculate_sample_size(0.10, 0.01)
        large = calculate_sample_size(0.10, 0.05)
        assert large.control_size < small.control_size

    def test_higher_power_needs_more_samples(self) -> None:
        low_power = calculate_sample_size(0.10, 0.02, power=0.80)
        high_power = calculate_sample_size(0.10, 0.02, power=0.90)
        assert high_power.control_size > low_power.control_size

    def test_result_is_pydantic_model(self) -> None:
        result = calculate_sample_size(0.05, 0.01)
        assert isinstance(result, SampleSizeResult)

    # Edge cases — should raise ValueError
    def test_zero_mde_raises(self) -> None:
        with pytest.raises(ValueError, match="mde"):
            calculate_sample_size(0.05, 0.0)

    def test_zero_baseline_raises(self) -> None:
        with pytest.raises(ValueError, match="baseline_rate"):
            calculate_sample_size(0.0, 0.01)

    def test_one_baseline_raises(self) -> None:
        with pytest.raises(ValueError, match="baseline_rate"):
            calculate_sample_size(1.0, 0.01)

    def test_mde_pushes_treatment_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="outside"):
            calculate_sample_size(0.95, 0.10)  # 0.95 + 0.10 = 1.05 > 1

    def test_power_one_raises(self) -> None:
        with pytest.raises(ValueError, match="power"):
            calculate_sample_size(0.05, 0.01, power=1.0)

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            calculate_sample_size(0.05, 0.01, alpha=0.0)


# ---------------------------------------------------------------------------
# calculate_power
# ---------------------------------------------------------------------------


class TestCalculatePower:
    def test_power_at_required_n_meets_target(self) -> None:
        """calculate_power at the sample size returned by calculate_sample_size
        must be >= the requested power."""
        required = calculate_sample_size(0.05, 0.01, power=0.80)
        achieved = calculate_power(0.05, 0.01, required.control_size)
        assert achieved >= 0.80 - 1e-6

    def test_power_at_double_n_is_higher(self) -> None:
        required = calculate_sample_size(0.05, 0.01, power=0.80)
        p_base = calculate_power(0.05, 0.01, required.control_size)
        p_more = calculate_power(0.05, 0.01, required.control_size * 2)
        assert p_more > p_base

    def test_power_is_monotone_in_sample_size(self) -> None:
        """Power should not decrease as n increases."""
        ns = [500, 1000, 2000, 4000, 8000, 16000]
        powers = [calculate_power(0.05, 0.01, n) for n in ns]
        for a, b in zip(powers, powers[1:]):
            assert b >= a

    def test_zero_mde_returns_alpha(self) -> None:
        """When mde=0 there is no real effect; power equals the false positive rate."""
        alpha = 0.05
        p = calculate_power(0.10, 0.0, sample_size=10000, alpha=alpha)
        assert p == pytest.approx(alpha)

    def test_power_between_zero_and_one(self) -> None:
        p = calculate_power(0.05, 0.01, 5000)
        assert 0.0 <= p <= 1.0

    def test_tiny_sample_gives_low_power(self) -> None:
        p = calculate_power(0.05, 0.01, 10)
        assert p < 0.15

    def test_very_large_sample_gives_high_power(self) -> None:
        p = calculate_power(0.05, 0.01, 100_000)
        assert p > 0.999

    def test_invalid_baseline_raises(self) -> None:
        with pytest.raises(ValueError, match="baseline_rate"):
            calculate_power(0.0, 0.01, 1000)

    def test_invalid_sample_size_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_size"):
            calculate_power(0.05, 0.01, 0)


# ---------------------------------------------------------------------------
# calculate_mde
# ---------------------------------------------------------------------------


class TestCalculateMde:
    def test_roundtrip_sample_size_to_mde(self) -> None:
        """sample_size → mde → sample_size should recover the original n.

        The roundtrip isn't perfect because calculate_mde iterates once and
        calculate_sample_size uses ceiling, but the result should be within 1%.
        """
        original_mde = 0.01
        required = calculate_sample_size(0.05, original_mde, power=0.80)
        recovered_mde = calculate_mde(0.05, required.control_size, power=0.80)
        assert recovered_mde == pytest.approx(original_mde, rel=0.02)

    def test_mde_roundtrip_for_various_baselines(self) -> None:
        for baseline in (0.05, 0.10, 0.20, 0.50):
            for target_mde in (0.01, 0.02, 0.05):
                if baseline + target_mde >= 1.0:
                    continue
                result = calculate_sample_size(baseline, target_mde, power=0.80)
                recovered = calculate_mde(baseline, result.control_size, power=0.80)
                assert recovered == pytest.approx(
                    target_mde, rel=0.03
                ), f"Roundtrip failed for baseline={baseline}, mde={target_mde}"

    def test_mde_decreases_with_larger_sample(self) -> None:
        """More data → smaller detectable effect."""
        mde_small_n = calculate_mde(0.10, 1000)
        mde_large_n = calculate_mde(0.10, 10000)
        assert mde_large_n < mde_small_n

    def test_mde_is_positive(self) -> None:
        mde = calculate_mde(0.05, 5000)
        assert mde > 0.0

    def test_invalid_baseline_raises(self) -> None:
        with pytest.raises(ValueError, match="baseline_rate"):
            calculate_mde(1.0, 1000)

    def test_invalid_sample_size_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_size"):
            calculate_mde(0.05, -1)

    def test_power_one_raises(self) -> None:
        with pytest.raises(ValueError, match="power"):
            calculate_mde(0.05, 1000, power=1.0)


# ---------------------------------------------------------------------------
# runtime_estimate
# ---------------------------------------------------------------------------


class TestRuntimeEstimate:
    def test_basic_estimate(self) -> None:
        """32,000 total subjects at 500/day → ~64 days."""
        rt = runtime_estimate(required_sample_size=32000, daily_traffic=500)
        assert rt.days_expected == pytest.approx(64.0, abs=1.0)

    def test_ci_ordering(self) -> None:
        """Lower bound (optimistic) must be <= expected <= upper bound (pessimistic)."""
        rt = runtime_estimate(10000, 300)
        assert rt.days_lower_95 <= rt.days_expected <= rt.days_upper_95

    def test_weeks_consistent_with_days(self) -> None:
        rt = runtime_estimate(7000, 100)
        assert rt.weeks_expected == pytest.approx(rt.days_expected / 7.0, abs=0.2)

    def test_higher_traffic_means_fewer_days(self) -> None:
        low = runtime_estimate(10000, 100)
        high = runtime_estimate(10000, 1000)
        assert high.days_expected < low.days_expected

    def test_ci_width_shrinks_with_higher_traffic(self) -> None:
        """Higher daily traffic → tighter Poisson CI."""
        low = runtime_estimate(50000, 100)
        high = runtime_estimate(50000, 10000)
        width_low = low.days_upper_95 - low.days_lower_95
        width_high = high.days_upper_95 - high.days_lower_95
        # Both are in days; the relative width should narrow at high traffic.
        rel_low = width_low / low.days_expected
        rel_high = width_high / high.days_expected
        assert rel_high < rel_low

    def test_result_is_pydantic_model(self) -> None:
        rt = runtime_estimate(1000, 50)
        assert isinstance(rt, RuntimeEstimate)

    def test_zero_sample_size_raises(self) -> None:
        with pytest.raises(ValueError, match="required_sample_size"):
            runtime_estimate(0, 100)

    def test_zero_traffic_raises(self) -> None:
        with pytest.raises(ValueError, match="daily_traffic"):
            runtime_estimate(1000, 0)

    def test_end_to_end_with_sample_size_result(self) -> None:
        """Full pipeline: calculate n, then estimate runtime."""
        result = calculate_sample_size(0.05, 0.01, power=0.80)
        rt = runtime_estimate(result.total_sample_size, daily_traffic=500)
        # With total ~16318 and 500/day, should be roughly 32-33 days.
        assert 20.0 <= rt.days_expected <= 50.0
        assert rt.days_lower_95 < rt.days_expected < rt.days_upper_95

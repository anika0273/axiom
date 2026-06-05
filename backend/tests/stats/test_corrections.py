"""Tests for backend/app/stats/corrections.py.

Reference derivations (α = 0.05, n = 5):

Known-answer BH — p = [0.001, 0.01, 0.05, 0.1, 0.2]:
    BH thresholds: (k+1)/5 × 0.05 = [0.010, 0.020, 0.030, 0.040, 0.050]
    Comparisons:   0.001≤0.010✓  0.010≤0.020✓  0.050≤0.030✗ → stop at k=1
    Reject indices 0 and 1.

Power ordering — p = [0.001, 0.01, 0.03, 0.04, 0.2]:
    Bonferroni adj: [0.005, 0.050, 0.150, 0.200, 1.000] → reject <0.05: [0]     → 1
    Holm adj (step-down max): [0.005, 0.040, 0.090, 0.090, 0.200] → <0.05: [0,1] → 2
    BH adj (step-up  min):   [0.005, 0.025, 0.050, 0.050, 0.200] → ≤0.05: [0,1,2,3] → 4
    Order: Bonferroni(1) < Holm(2) < BH(4).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from app.stats.corrections import (
    CorrectionComparison,
    CorrectionRecommendation,
    apply_multiple_correction,
    compare_corrections,
    recommend_correction,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def known_p() -> np.ndarray:
    """Known-answer BH test case: p = [0.001, 0.01, 0.05, 0.1, 0.2]."""
    return np.array([0.001, 0.01, 0.05, 0.1, 0.2])


@pytest.fixture()
def ordering_p() -> np.ndarray:
    """Strict ordering test case: p = [0.001, 0.01, 0.03, 0.04, 0.2]."""
    return np.array([0.001, 0.01, 0.03, 0.04, 0.2])


# ---------------------------------------------------------------------------
# Known-answer BH test
# ---------------------------------------------------------------------------


class TestBHKnownAnswer:
    def test_reject_exactly_two(self, known_p: np.ndarray) -> None:
        """BH rejects exactly indices 0 and 1 for the reference case."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(known_p, method="fdr_bh", alpha=0.05)
        assert result.n_rejected == 2

    def test_correct_indices_rejected(self, known_p: np.ndarray) -> None:
        """Rejections are exactly p=0.001 and p=0.010, not p=0.05."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(known_p, method="fdr_bh", alpha=0.05)
        assert result.reject_mask[0] is np.bool_(True)
        assert result.reject_mask[1] is np.bool_(True)
        assert result.reject_mask[2] is np.bool_(False)
        assert result.reject_mask[3] is np.bool_(False)
        assert result.reject_mask[4] is np.bool_(False)

    def test_q_value_at_boundary(self, known_p: np.ndarray) -> None:
        """BH q-value for p=0.05 (rank 3) exceeds α=0.05 → not rejected."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(known_p, method="fdr_bh", alpha=0.05)
        # q[2] = 0.05 × 5 / 3 ≈ 0.0833 > 0.05
        assert result.corrected_p[2] > 0.05

    def test_corrected_p_order_preserved(self, known_p: np.ndarray) -> None:
        """corrected_p is in the same order as the input (not sorted)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(known_p, method="fdr_bh", alpha=0.05)
        assert len(result.corrected_p) == len(known_p)
        # Smallest original p should still have smallest corrected p.
        assert result.corrected_p[0] < result.corrected_p[-1]

    def test_fdr_upper_bound_is_alpha(self, known_p: np.ndarray) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(known_p, method="fdr_bh", alpha=0.05)
        assert result.fdr_upper_bound == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# Power ordering: Bonferroni ≤ Holm ≤ BH
# ---------------------------------------------------------------------------


class TestPowerOrdering:
    def test_bonferroni_most_conservative(self, ordering_p: np.ndarray) -> None:
        """Bonferroni rejects fewer hypotheses than Holm for ordering_p."""
        bon = apply_multiple_correction(ordering_p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(ordering_p, "holm_bonferroni")
        assert bon.n_rejected < holm.n_rejected

    def test_holm_less_conservative_than_bh(self, ordering_p: np.ndarray) -> None:
        """Holm rejects fewer hypotheses than BH for ordering_p."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(ordering_p, "holm_bonferroni")
            bh = apply_multiple_correction(ordering_p, "fdr_bh")
        assert holm.n_rejected < bh.n_rejected

    def test_strict_three_way_ordering(self, ordering_p: np.ndarray) -> None:
        """Bonferroni(1) < Holm(2) < BH(4) for the reference ordering_p."""
        bon = apply_multiple_correction(ordering_p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(ordering_p, "holm_bonferroni")
            bh = apply_multiple_correction(ordering_p, "fdr_bh")
        assert bon.n_rejected == 1
        assert holm.n_rejected == 2
        assert bh.n_rejected == 4

    def test_bonferroni_fwer_bound(self, ordering_p: np.ndarray) -> None:
        """Bonferroni and Holm both report fwer_upper_bound = alpha."""
        bon = apply_multiple_correction(ordering_p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(ordering_p, "holm_bonferroni")
        assert bon.fwer_upper_bound == pytest.approx(0.05)
        assert holm.fwer_upper_bound == pytest.approx(0.05)

    def test_bh_fwer_not_alpha(self, ordering_p: np.ndarray) -> None:
        """BH fwer_upper_bound is a loose bound (n×α), not α."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            bh = apply_multiple_correction(ordering_p, "fdr_bh")
        n = len(ordering_p)
        assert bh.fwer_upper_bound == pytest.approx(min(n * 0.05, 1.0))


# ---------------------------------------------------------------------------
# Bonferroni manual verification
# ---------------------------------------------------------------------------


class TestBonferroniCorrection:
    def test_adjusted_p_formula(self) -> None:
        """p_adj[i] = min(p[i] × n, 1.0)."""
        p = np.array([0.01, 0.04, 0.2])
        result = apply_multiple_correction(p, "bonferroni")
        expected = np.array([0.03, 0.12, 0.60])
        np.testing.assert_allclose(result.corrected_p, expected, rtol=1e-9)

    def test_clamped_at_one(self) -> None:
        """p × n > 1 is clamped to 1.0."""
        p = np.array([0.4, 0.6])
        result = apply_multiple_correction(p, "bonferroni")
        assert result.corrected_p[0] == pytest.approx(0.8)
        assert result.corrected_p[1] == pytest.approx(1.0)

    def test_all_rejected_when_all_tiny(self) -> None:
        """All hypotheses rejected when all p × n < α."""
        p = np.array([0.001, 0.002, 0.003])
        result = apply_multiple_correction(p, "bonferroni")
        assert result.n_rejected == 3
        assert all(result.reject_mask)

    def test_none_rejected_when_all_large(self) -> None:
        p = np.array([0.3, 0.5, 0.8])
        result = apply_multiple_correction(p, "bonferroni")
        assert result.n_rejected == 0
        assert not any(result.reject_mask)

    def test_method_label(self) -> None:
        p = np.array([0.01, 0.02])
        result = apply_multiple_correction(p, "bonferroni")
        assert result.method == "bonferroni"

    def test_original_p_unchanged(self) -> None:
        """original_p in result matches input order."""
        p = np.array([0.05, 0.01, 0.1])
        result = apply_multiple_correction(p, "bonferroni")
        np.testing.assert_array_equal(result.original_p, p)


# ---------------------------------------------------------------------------
# Holm manual verification
# ---------------------------------------------------------------------------


class TestHolmCorrection:
    def test_adjusted_p_step_down(self) -> None:
        """Adjusted p-values respect cumulative-max monotonicity."""
        p = np.array([0.001, 0.01, 0.05, 0.1, 0.2])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "holm_bonferroni")
        # Corrected p-values must be non-decreasing after sorting by original p.
        sort_idx = np.argsort(result.original_p)
        sorted_corrected = result.corrected_p[sort_idx]
        assert np.all(np.diff(sorted_corrected) >= 0)

    def test_holm_strictly_better_than_bonferroni(self) -> None:
        """There exists a p-value set where Holm rejects more than Bonferroni."""
        p = np.array([0.001, 0.01, 0.03, 0.04, 0.2])
        bon = apply_multiple_correction(p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(p, "holm_bonferroni")
        assert holm.n_rejected > bon.n_rejected

    def test_method_label(self) -> None:
        p = np.array([0.01, 0.02])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "holm_bonferroni")
        assert result.method == "holm_bonferroni"

    def test_unsorted_input_same_as_sorted(self) -> None:
        """Holm gives the same n_rejected for shuffled and sorted inputs."""
        p_sorted = np.array([0.001, 0.01, 0.05, 0.1, 0.2])
        p_shuffled = np.array([0.1, 0.001, 0.2, 0.05, 0.01])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            r_sorted = apply_multiple_correction(p_sorted, "holm_bonferroni")
            r_shuffled = apply_multiple_correction(p_shuffled, "holm_bonferroni")
        assert r_sorted.n_rejected == r_shuffled.n_rejected

    def test_reject_mask_matches_corrected_p(self) -> None:
        """reject_mask is consistent with corrected_p < alpha."""
        p = np.array([0.005, 0.02, 0.1, 0.3])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "holm_bonferroni")
        np.testing.assert_array_equal(result.reject_mask, result.corrected_p < 0.05)


# ---------------------------------------------------------------------------
# BH manual verification
# ---------------------------------------------------------------------------


class TestBHCorrection:
    def test_unsorted_input_same_rejections(self) -> None:
        """BH produces the same reject set for shuffled input."""
        p_sorted = np.array([0.001, 0.01, 0.03, 0.04, 0.2])
        p_shuffled = np.array([0.04, 0.001, 0.2, 0.03, 0.01])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            r_sorted = apply_multiple_correction(p_sorted, "fdr_bh")
            r_shuffled = apply_multiple_correction(p_shuffled, "fdr_bh")
        assert r_sorted.n_rejected == r_shuffled.n_rejected

    def test_q_values_monotone(self) -> None:
        """BH q-values are non-decreasing in the order of the sorted p-values."""
        p = np.array([0.003, 0.015, 0.04, 0.09, 0.25])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "fdr_bh")
        sort_idx = np.argsort(result.original_p)
        sorted_q = result.corrected_p[sort_idx]
        assert np.all(np.diff(sorted_q) >= -1e-12)

    def test_prds_warning_emitted(self) -> None:
        """UserWarning is emitted when BH is applied to more than one test."""
        p = np.array([0.01, 0.04])
        with pytest.warns(UserWarning, match="PRDS"):
            apply_multiple_correction(p, "fdr_bh")

    def test_no_warning_for_single_test(self) -> None:
        """No UserWarning for a single-test BH call."""
        p = np.array([0.03])
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            result = apply_multiple_correction(p, "fdr_bh")
        assert result.n_rejected == 1

    def test_reject_mask_uses_leq(self) -> None:
        """BH rejects when q-value == alpha (≤, not strict <)."""
        # Construct p so that q-value for an index is exactly alpha.
        # q[k] = p[k] × n/(k+1). For q[2]=0.05: p[2] = 0.05 × 3/5 = 0.03
        # and q[2] must survive step-up: needs q[3] ≥ q[2].
        p = np.array([0.001, 0.01, 0.03, 0.04, 0.2])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "fdr_bh")
        # q[2] = 0.03 × 5/3 = 0.05, and after step-up min, stays 0.05 → rejected
        assert result.reject_mask[2]


# ---------------------------------------------------------------------------
# compare_corrections
# ---------------------------------------------------------------------------


class TestCompareCorrections:
    def test_returns_comparison_object(self, ordering_p: np.ndarray) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            comp = compare_corrections(ordering_p)
        assert isinstance(comp, CorrectionComparison)

    def test_summary_contains_most_powerful(self, ordering_p: np.ndarray) -> None:
        """Summary names BH as most powerful when it rejects more than Bonferroni."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            comp = compare_corrections(ordering_p)
        assert "BH" in comp.summary
        assert "most powerful" in comp.summary

    def test_summary_contains_most_conservative(self, ordering_p: np.ndarray) -> None:
        """Summary names Bonferroni as most conservative for ordering_p."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            comp = compare_corrections(ordering_p)
        assert "Bonferroni" in comp.summary
        assert "most conservative" in comp.summary

    def test_all_methods_present(self, ordering_p: np.ndarray) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            comp = compare_corrections(ordering_p)
        assert comp.bonferroni.method == "bonferroni"
        assert comp.holm.method == "holm_bonferroni"
        assert comp.fdr_bh.method == "fdr_bh"

    def test_summary_all_agree(self) -> None:
        """When all methods give the same result, summary says 'all methods agree'."""
        p = np.array([0.001])  # single test → all methods identical
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            comp = compare_corrections(p)
        assert "all methods agree" in comp.summary.lower()

    def test_rejection_counts_in_summary(self, ordering_p: np.ndarray) -> None:
        """Summary includes numeric rejection counts for each method."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            comp = compare_corrections(ordering_p)
        assert "1" in comp.summary  # Bonferroni: 1 rejection
        assert "2" in comp.summary  # Holm: 2 rejections
        assert "4" in comp.summary  # BH: 4 rejections


# ---------------------------------------------------------------------------
# recommend_correction
# ---------------------------------------------------------------------------


class TestRecommendCorrection:
    def test_confirmatory_small_returns_bonferroni(self) -> None:
        """n=3, confirmatory → Bonferroni."""
        rec = recommend_correction(3, "confirmatory")
        assert rec.method == "bonferroni"

    def test_exploratory_large_returns_bh(self) -> None:
        """n=50, exploratory → BH."""
        rec = recommend_correction(50, "exploratory")
        assert rec.method == "fdr_bh"

    def test_production_small_returns_bonferroni(self) -> None:
        """n=5, production → Bonferroni (≤ 10 metrics)."""
        rec = recommend_correction(5, "production")
        assert rec.method == "bonferroni"

    def test_production_large_returns_holm(self) -> None:
        """n=20, production → Holm (> 10 metrics)."""
        rec = recommend_correction(20, "production")
        assert rec.method == "holm_bonferroni"

    def test_single_test_no_power_loss(self) -> None:
        """n=1 → zero expected power loss regardless of context."""
        for ctx in ("confirmatory", "exploratory", "production"):
            rec = recommend_correction(1, ctx)
            assert rec.expected_power_loss_pct == pytest.approx(0.0)

    def test_power_loss_increases_with_n(self) -> None:
        """More tests → higher expected power loss for the same context."""
        r3 = recommend_correction(3, "confirmatory")
        r10 = recommend_correction(10, "confirmatory")
        assert r10.expected_power_loss_pct > r3.expected_power_loss_pct

    def test_bh_less_power_loss_than_bonferroni(self) -> None:
        """For equal n, BH has lower expected power loss than Bonferroni."""
        n = 20
        bon = recommend_correction(n, "confirmatory")
        bh = recommend_correction(n, "exploratory")
        assert bh.expected_power_loss_pct < bon.expected_power_loss_pct

    def test_returns_recommendation_object(self) -> None:
        rec = recommend_correction(5, "exploratory")
        assert isinstance(rec, CorrectionRecommendation)
        assert len(rec.reasoning) > 0

    def test_invalid_n_raises(self) -> None:
        with pytest.raises(ValueError, match="n_tests"):
            recommend_correction(0, "confirmatory")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_test_bonferroni_noop(self) -> None:
        """n=1: Bonferroni corrected p equals original p."""
        p = np.array([0.03])
        result = apply_multiple_correction(p, "bonferroni")
        assert result.corrected_p[0] == pytest.approx(0.03)
        assert result.n_rejected == 1

    def test_single_test_holm_noop(self) -> None:
        """n=1: Holm corrected p equals original p."""
        p = np.array([0.03])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "holm_bonferroni")
        assert result.corrected_p[0] == pytest.approx(0.03)
        assert result.n_rejected == 1

    def test_single_test_bh_noop(self) -> None:
        """n=1: BH corrected p equals original p."""
        p = np.array([0.03])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(p, "fdr_bh")
        assert result.corrected_p[0] == pytest.approx(0.03)

    def test_all_p_zero_all_rejected(self) -> None:
        """All p=0 → all hypotheses rejected by every method."""
        p = np.zeros(5)
        bon = apply_multiple_correction(p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(p, "holm_bonferroni")
            bh = apply_multiple_correction(p, "fdr_bh")
        assert bon.n_rejected == 5
        assert holm.n_rejected == 5
        assert bh.n_rejected == 5

    def test_all_p_one_none_rejected(self) -> None:
        """All p=1 → no hypotheses rejected by any method."""
        p = np.ones(5)
        bon = apply_multiple_correction(p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(p, "holm_bonferroni")
            bh = apply_multiple_correction(p, "fdr_bh")
        assert bon.n_rejected == 0
        assert holm.n_rejected == 0
        assert bh.n_rejected == 0

    def test_list_input_accepted(self) -> None:
        """Python list is coerced to ndarray without error."""
        result = apply_multiple_correction([0.01, 0.04, 0.2], "bonferroni")
        assert result.n_rejected >= 0

    def test_all_identical_p(self) -> None:
        """Equal p-values — no index errors."""
        p = np.full(4, 0.025)
        bon = apply_multiple_correction(p, "bonferroni")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            holm = apply_multiple_correction(p, "holm_bonferroni")
            bh = apply_multiple_correction(p, "fdr_bh")
        # All methods should produce valid results.
        assert 0 <= bon.n_rejected <= 4
        assert 0 <= holm.n_rejected <= 4
        assert 0 <= bh.n_rejected <= 4

    def test_alpha_boundary_not_rejected_bonferroni(self) -> None:
        """Bonferroni: p_adj exactly equal to alpha is NOT rejected (strict <)."""
        # p[0] = 0.025, n=2 → p_adj = 0.05 exactly.
        p = np.array([0.025, 0.8])
        result = apply_multiple_correction(p, "bonferroni", alpha=0.05)
        assert not result.reject_mask[0]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_empty_array_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            apply_multiple_correction(np.array([]), "bonferroni")

    def test_nan_raises(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            apply_multiple_correction(np.array([0.05, np.nan]), "bonferroni")

    def test_inf_raises(self) -> None:
        with pytest.raises(ValueError, match="NaN or infinity"):
            apply_multiple_correction(np.array([0.05, np.inf]), "bonferroni")

    def test_negative_p_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            apply_multiple_correction(np.array([-0.01, 0.5]), "bonferroni")

    def test_p_greater_than_one_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            apply_multiple_correction(np.array([0.5, 1.1]), "bonferroni")

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            apply_multiple_correction(np.array([0.05]), "bonferroni", alpha=1.5)

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown method"):
            apply_multiple_correction(np.array([0.05]), "by_correction")  # type: ignore[arg-type]

    def test_compare_corrections_invalid_alpha(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            compare_corrections(np.array([0.01, 0.05]), alpha=0.0)

    def test_recommend_correction_zero_tests(self) -> None:
        with pytest.raises(ValueError, match="n_tests"):
            recommend_correction(0, "exploratory")

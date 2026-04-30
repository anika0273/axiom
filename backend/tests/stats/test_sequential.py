"""Tests for backend/app/stats/sequential.py.

Reference values (α = 0.05, two-sided, z_crit = norm.ppf(0.975) ≈ 1.95996):

    z*(t)  = z_crit / √t
    z_f(t) = (z_crit − norm.ppf(0.80)) · √t   ≈ 1.118 · √t

    t = 0.10 → z* ≈ 6.198,  z_f ≈ 0.354
    t = 0.20 → z* ≈ 4.382,  z_f ≈ 0.500
    t = 0.25 → z* ≈ 3.920,  z_f ≈ 0.559
    t = 0.30 → z* ≈ 3.578,  z_f ≈ 0.613
    t = 0.50 → z* ≈ 2.772,  z_f ≈ 0.791
    t = 1.00 → z* ≈ 1.960,  z_f ≈ 1.118

Test-case derivations:
  CONTINUE at look 2/10: z = 2.0, t = 0.2, boundary = 4.38 → 2.0 < 4.38 ✓
  STOP_WIN at look 3/10: z = 3.8, t = 0.3, boundary = 3.578 → 3.8 > 3.578 ✓
  STOP_LOSE at look 1/10: z = 0.1, t = 0.1, futility = 0.354 → 0.1 < 0.354 ✓
"""

from __future__ import annotations

import pytest
from scipy.stats import norm

from app.stats.sequential import (
    SequentialBoundaries,
    SequentialDecision,
    compute_obrien_fleming_boundaries,
    evaluate_interim_look,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def b10() -> SequentialBoundaries:
    """10 equally spaced looks, n=1 000 per group, α=0.05, two-sided."""
    return compute_obrien_fleming_boundaries(1000, 10, alpha=0.05, two_sided=True)


@pytest.fixture()
def b5() -> SequentialBoundaries:
    """5 equally spaced looks, n=1 000 per group, α=0.05, two-sided."""
    return compute_obrien_fleming_boundaries(1000, 5, alpha=0.05, two_sided=True)


@pytest.fixture()
def b10_one_sided() -> SequentialBoundaries:
    """10 looks, one-sided α=0.05."""
    return compute_obrien_fleming_boundaries(1000, 10, alpha=0.05, two_sided=False)


# ---------------------------------------------------------------------------
# compute_obrien_fleming_boundaries — boundary properties
# ---------------------------------------------------------------------------


class TestComputeOBFBoundaries:
    def test_early_look_requires_large_z(self, b10: SequentialBoundaries) -> None:
        """Look 1/10 (t=0.1): z* ≈ 6.20 — well above 3.5."""
        assert b10.z_boundary_per_look[0] > 3.5

    def test_early_look_exact_value(self, b10: SequentialBoundaries) -> None:
        expected = norm.ppf(0.975) / 0.1 ** 0.5
        assert b10.z_boundary_per_look[0] == pytest.approx(expected, rel=1e-6)

    def test_final_look_below_two(self, b10: SequentialBoundaries) -> None:
        """Final look (t=1.0): z* ≈ 1.96 < 2.0."""
        assert b10.z_boundary_per_look[-1] < 2.0

    def test_final_look_exact_value(self, b10: SequentialBoundaries) -> None:
        assert b10.z_boundary_per_look[-1] == pytest.approx(norm.ppf(0.975), rel=1e-6)

    def test_all_early_looks_exceed_3(self, b10: SequentialBoundaries) -> None:
        """All looks with t < 0.25 must have z-boundary > 3.0."""
        for t, z in zip(b10.info_fraction_per_look, b10.z_boundary_per_look):
            if t < 0.25:
                assert z > 3.0, f"t={t}: z={z:.3f} ≤ 3.0"

    def test_total_alpha_spent_equals_alpha(self, b10: SequentialBoundaries) -> None:
        """Telescoping sum of incremental alphas must equal the total budget."""
        assert sum(b10.alpha_spent_per_look) == pytest.approx(0.05, abs=1e-9)

    def test_total_alpha_spent_various_looks(self) -> None:
        for k in [1, 3, 5, 20]:
            b = compute_obrien_fleming_boundaries(1000, k, alpha=0.05, two_sided=True)
            assert sum(b.alpha_spent_per_look) == pytest.approx(0.05, abs=1e-9)

    def test_total_alpha_spent_for_alpha_01(self) -> None:
        b = compute_obrien_fleming_boundaries(500, 8, alpha=0.01, two_sided=True)
        assert sum(b.alpha_spent_per_look) == pytest.approx(0.01, abs=1e-9)

    def test_z_boundaries_strictly_decreasing(self, b10: SequentialBoundaries) -> None:
        z = b10.z_boundary_per_look
        for i in range(len(z) - 1):
            assert z[i] > z[i + 1], f"z[{i}]={z[i]:.4f} ≤ z[{i+1}]={z[i+1]:.4f}"

    def test_info_fractions_evenly_spaced(self, b10: SequentialBoundaries) -> None:
        expected = [k / 10 for k in range(1, 11)]
        for actual, exp in zip(b10.info_fraction_per_look, expected):
            assert actual == pytest.approx(exp, rel=1e-9)

    def test_info_fraction_final_look_is_one(self, b10: SequentialBoundaries) -> None:
        assert b10.info_fraction_per_look[-1] == pytest.approx(1.0)

    def test_all_arrays_have_length_k(self, b10: SequentialBoundaries) -> None:
        assert len(b10.alpha_spent_per_look) == 10
        assert len(b10.z_boundary_per_look) == 10
        assert len(b10.info_fraction_per_look) == 10
        assert len(b10.futility_boundaries) == 10

    def test_five_looks_arrays_have_length_5(self, b5: SequentialBoundaries) -> None:
        assert len(b5.z_boundary_per_look) == 5

    def test_single_look_equals_normal_z(self) -> None:
        """One look (no interim): boundary = z_{α/2} and alpha spent = α."""
        b = compute_obrien_fleming_boundaries(1000, 1, alpha=0.05, two_sided=True)
        assert b.z_boundary_per_look[0] == pytest.approx(norm.ppf(0.975), rel=1e-6)
        assert sum(b.alpha_spent_per_look) == pytest.approx(0.05, abs=1e-9)

    def test_one_sided_boundaries_lower_than_two_sided(
        self, b10: SequentialBoundaries, b10_one_sided: SequentialBoundaries
    ) -> None:
        """One-sided z_α < two-sided z_{α/2} at every look."""
        for z_two, z_one in zip(b10.z_boundary_per_look, b10_one_sided.z_boundary_per_look):
            assert z_one < z_two

    def test_futility_boundaries_strictly_increasing(
        self, b10: SequentialBoundaries
    ) -> None:
        """More data → tighter futility threshold (larger |z| needed to avoid stop)."""
        f = b10.futility_boundaries
        for i in range(len(f) - 1):
            assert f[i] < f[i + 1], f"f[{i}]={f[i]:.4f} ≥ f[{i+1}]={f[i+1]:.4f}"

    def test_futility_boundary_at_t01(self, b10: SequentialBoundaries) -> None:
        # z_f(0.1) = (1.95996 − 0.842) · √0.1 ≈ 0.354
        expected = (norm.ppf(0.975) - norm.ppf(0.80)) * 0.1 ** 0.5
        assert b10.futility_boundaries[0] == pytest.approx(expected, rel=1e-5)

    def test_stored_parameters_match_inputs(self) -> None:
        b = compute_obrien_fleming_boundaries(750, 7, alpha=0.01, two_sided=False)
        assert b.total_planned_n == 750
        assert b.n_interim_looks == 7
        assert b.alpha == pytest.approx(0.01)
        assert b.two_sided is False

    def test_result_is_sequential_boundaries_instance(
        self, b10: SequentialBoundaries
    ) -> None:
        assert isinstance(b10, SequentialBoundaries)

    # Validation errors
    def test_zero_total_n_raises(self) -> None:
        with pytest.raises(ValueError, match="total_planned_n"):
            compute_obrien_fleming_boundaries(0, 5)

    def test_negative_total_n_raises(self) -> None:
        with pytest.raises(ValueError, match="total_planned_n"):
            compute_obrien_fleming_boundaries(-100, 5)

    def test_zero_looks_raises(self) -> None:
        with pytest.raises(ValueError, match="n_interim_looks"):
            compute_obrien_fleming_boundaries(1000, 0)

    def test_alpha_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            compute_obrien_fleming_boundaries(1000, 5, alpha=0.0)

    def test_alpha_one_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            compute_obrien_fleming_boundaries(1000, 5, alpha=1.0)

    def test_alpha_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            compute_obrien_fleming_boundaries(1000, 5, alpha=-0.05)


# ---------------------------------------------------------------------------
# evaluate_interim_look — decision logic
# ---------------------------------------------------------------------------


class TestEvaluateInterimLook:
    def test_continue_when_z_below_boundary_look_2(
        self, b10: SequentialBoundaries
    ) -> None:
        """z=2.0 at look 2/10 (t=0.2, boundary≈4.38): must CONTINUE."""
        decision = evaluate_interim_look(2.0, 200, b10)
        assert decision.decision == "CONTINUE"

    def test_stop_win_when_z_exceeds_boundary_look_3(
        self, b10: SequentialBoundaries
    ) -> None:
        """z=3.8 at look 3/10 (t=0.3, boundary≈3.578): must STOP_WIN."""
        decision = evaluate_interim_look(3.8, 300, b10)
        assert decision.decision == "STOP_WIN"

    def test_first_look_requires_extreme_z(self, b10: SequentialBoundaries) -> None:
        """At look 1/10 (boundary≈6.20), z=5.5 is insufficient → CONTINUE."""
        decision = evaluate_interim_look(5.5, 100, b10)
        assert decision.decision == "CONTINUE"
        assert decision.required_z > 5.5

    def test_first_look_stop_win_with_very_large_z(
        self, b10: SequentialBoundaries
    ) -> None:
        """z=7.0 clears the look-1 boundary (≈6.20) → STOP_WIN."""
        decision = evaluate_interim_look(7.0, 100, b10)
        assert decision.decision == "STOP_WIN"

    def test_negative_z_triggers_stop_win_two_sided(
        self, b10: SequentialBoundaries
    ) -> None:
        """Two-sided: z=-3.8 → |z|=3.8 > 3.578 at t=0.3 → STOP_WIN."""
        decision = evaluate_interim_look(-3.8, 300, b10)
        assert decision.decision == "STOP_WIN"

    def test_continue_between_boundaries_at_half_information(
        self, b10: SequentialBoundaries
    ) -> None:
        """At t=0.5 boundary≈2.77, futility≈0.79: z=2.0 is between → CONTINUE."""
        decision = evaluate_interim_look(2.0, 500, b10)
        assert decision.decision == "CONTINUE"

    def test_futility_triggers_at_look_1_with_near_zero_z(
        self, b10: SequentialBoundaries
    ) -> None:
        """z=0.1 at look 1/10 (t=0.1, futility≈0.354): 0.1 < 0.354 → STOP_LOSE."""
        decision = evaluate_interim_look(0.1, 100, b10)
        assert decision.decision == "STOP_LOSE"

    def test_futility_triggers_at_midpoint_with_zero_z(
        self, b10: SequentialBoundaries
    ) -> None:
        """z=0.0 at t=0.5 (futility≈0.79): 0.0 < 0.79 → STOP_LOSE."""
        decision = evaluate_interim_look(0.0, 500, b10)
        assert decision.decision == "STOP_LOSE"

    def test_current_n_exceeds_total_n_clamps_to_one(
        self, b10: SequentialBoundaries
    ) -> None:
        """current_n=1200 > total=1000: info fraction clamped to 1.0, no error."""
        decision = evaluate_interim_look(1.5, 1200, b10)
        assert decision.info_fraction_complete == pytest.approx(1.0)

    def test_current_n_exceeds_total_n_uses_final_boundary(
        self, b10: SequentialBoundaries
    ) -> None:
        """After clamping to t=1.0, boundary = z_{α/2} ≈ 1.96."""
        decision = evaluate_interim_look(1.5, 1200, b10)
        assert decision.required_z == pytest.approx(norm.ppf(0.975), rel=1e-4)
        # z=1.5 < 1.96 → CONTINUE
        assert decision.decision == "CONTINUE"

    def test_one_sided_negative_z_triggers_futility(
        self, b10_one_sided: SequentialBoundaries
    ) -> None:
        """One-sided: z=-2.0 at t=0.5 — not beneficial, clearly futile → STOP_LOSE."""
        # z_f(t=0.5, one-sided) = (norm.ppf(0.95) − norm.ppf(0.80)) · √0.5 ≈ 0.568
        # test_stat = z_current = -2.0 ≤ 0.568 → STOP_LOSE
        decision = evaluate_interim_look(-2.0, 500, b10_one_sided)
        assert decision.decision == "STOP_LOSE"

    def test_info_fraction_computed_correctly(self, b10: SequentialBoundaries) -> None:
        decision = evaluate_interim_look(2.0, 300, b10)
        assert decision.info_fraction_complete == pytest.approx(0.3, rel=1e-6)

    def test_required_z_matches_obf_formula(self, b10: SequentialBoundaries) -> None:
        """required_z = z_{α/2} / √t at the current info fraction."""
        decision = evaluate_interim_look(2.0, 500, b10)
        expected = norm.ppf(0.975) / 0.5 ** 0.5
        assert decision.required_z == pytest.approx(expected, rel=1e-4)

    def test_required_z_at_final_look(self, b10: SequentialBoundaries) -> None:
        decision = evaluate_interim_look(2.0, 1000, b10)
        assert decision.required_z == pytest.approx(norm.ppf(0.975), rel=1e-4)
        assert decision.required_z < 2.0

    def test_current_z_preserved_in_result(self, b10: SequentialBoundaries) -> None:
        decision = evaluate_interim_look(2.345, 500, b10)
        assert decision.current_z == pytest.approx(2.345)

    def test_interpretation_is_nonempty_string(self, b10: SequentialBoundaries) -> None:
        for z_val in [0.1, 2.0, 3.8, -3.8]:
            d = evaluate_interim_look(z_val, 300, b10)
            assert isinstance(d.interpretation, str)
            assert len(d.interpretation) > 30

    def test_stop_win_interpretation_mentions_boundary(
        self, b10: SequentialBoundaries
    ) -> None:
        d = evaluate_interim_look(3.8, 300, b10)
        assert "boundary" in d.interpretation.lower()
        assert "winner" in d.interpretation.lower()

    def test_stop_lose_interpretation_mentions_power(
        self, b10: SequentialBoundaries
    ) -> None:
        d = evaluate_interim_look(0.1, 100, b10)
        assert "power" in d.interpretation.lower()

    def test_continue_interpretation_mentions_continue(
        self, b10: SequentialBoundaries
    ) -> None:
        d = evaluate_interim_look(2.0, 300, b10)
        assert "continue" in d.interpretation.lower()

    def test_result_is_sequential_decision_instance(
        self, b10: SequentialBoundaries
    ) -> None:
        d = evaluate_interim_look(2.0, 300, b10)
        assert isinstance(d, SequentialDecision)

    def test_zero_current_n_raises(self, b10: SequentialBoundaries) -> None:
        with pytest.raises(ValueError, match="current_n"):
            evaluate_interim_look(2.0, 0, b10)

    def test_negative_current_n_raises(self, b10: SequentialBoundaries) -> None:
        with pytest.raises(ValueError, match="current_n"):
            evaluate_interim_look(2.0, -1, b10)


# ---------------------------------------------------------------------------
# Mathematical consistency checks
# ---------------------------------------------------------------------------


class TestOBFMathematicalProperties:
    def test_alpha_spending_is_non_negative_per_look(
        self, b10: SequentialBoundaries
    ) -> None:
        for delta in b10.alpha_spent_per_look:
            assert delta >= 0.0

    def test_alpha_spending_increases_with_more_data(
        self, b10: SequentialBoundaries
    ) -> None:
        """Later looks spend more incremental alpha (more power available)."""
        alphas = b10.alpha_spent_per_look
        # Cumulative spending is monotonically increasing
        cum = 0.0
        prev_cum = -1.0
        for delta in alphas:
            cum += delta
            assert cum > prev_cum
            prev_cum = cum

    def test_boundary_at_t025_exceeds_3(self) -> None:
        """Spec requirement: t < 0.25 → z > 3.0."""
        b = compute_obrien_fleming_boundaries(1000, 4, alpha=0.05, two_sided=True)
        # Look 1/4 has t=0.25, exactly at the threshold; z*(0.25) ≈ 3.92
        assert b.z_boundary_per_look[0] > 3.0

    def test_roundtrip_single_look_versus_z_test(self) -> None:
        """With one look, the sequential test reduces to a standard z-test."""
        b = compute_obrien_fleming_boundaries(1000, 1, alpha=0.05, two_sided=True)
        # STOP_WIN at z=2.0 (> 1.96)
        d_win = evaluate_interim_look(2.0, 1000, b)
        assert d_win.decision == "STOP_WIN"
        # CONTINUE at z=1.9 (< 1.96)
        d_cnt = evaluate_interim_look(1.9, 1000, b)
        assert d_cnt.decision == "CONTINUE"

    def test_boundaries_scale_with_alpha(self) -> None:
        """Smaller alpha → higher (more conservative) boundaries everywhere."""
        b_05 = compute_obrien_fleming_boundaries(1000, 10, alpha=0.05, two_sided=True)
        b_01 = compute_obrien_fleming_boundaries(1000, 10, alpha=0.01, two_sided=True)
        for z_05, z_01 in zip(b_05.z_boundary_per_look, b_01.z_boundary_per_look):
            assert z_01 > z_05

    def test_evaluate_consistent_with_precomputed_boundaries(
        self, b10: SequentialBoundaries
    ) -> None:
        """required_z from evaluate_interim_look must match precomputed z for exact looks."""
        for t, z_pre in zip(
            b10.info_fraction_per_look, b10.z_boundary_per_look
        ):
            n = round(t * b10.total_planned_n)
            d = evaluate_interim_look(0.0, n, b10)
            assert d.required_z == pytest.approx(z_pre, rel=1e-4), (
                f"Mismatch at t={t}: precomputed={z_pre:.4f}, evaluated={d.required_z:.4f}"
            )

    def test_futility_boundary_formula(self, b10: SequentialBoundaries) -> None:
        """Verify futility_boundaries match the closed-form formula."""
        z_crit = norm.ppf(0.975)
        z_beta = norm.ppf(0.80)
        for t, z_f in zip(b10.info_fraction_per_look, b10.futility_boundaries):
            expected = max(0.0, (z_crit - z_beta) * t ** 0.5)
            assert z_f == pytest.approx(expected, rel=1e-5)

    def test_just_above_futility_is_continue(self, b10: SequentialBoundaries) -> None:
        """A z-stat just above the futility boundary should CONTINUE, not STOP_LOSE."""
        # At t=0.5, futility ≈ 0.791; z=0.9 > 0.791 and 0.9 < 2.772 → CONTINUE
        decision = evaluate_interim_look(0.9, 500, b10)
        assert decision.decision == "CONTINUE"

    def test_just_below_efficacy_is_continue(self, b10: SequentialBoundaries) -> None:
        """A z-stat just below the efficacy boundary should CONTINUE, not STOP_WIN."""
        # At t=0.3, boundary ≈ 3.578; z=3.5 < 3.578 → CONTINUE
        decision = evaluate_interim_look(3.5, 300, b10)
        assert decision.decision == "CONTINUE"

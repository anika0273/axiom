"""Integration test: full stats pipeline for a shopping cart A/B experiment.

Scenario
--------
An e-commerce platform runs an A/B test on a checkout button redesign.

    Traffic       : 5,000 users per group (10,000 total observed at interim)
    Planned n     : 10,000 per group (two-look sequential plan)
    Primary metric: purchase conversion (binary) — 5.0% baseline, 6.5% observed
    Secondary     : revenue per user (continuous) — 0.3-unit treatment uplift
    Null metrics  : add-to-cart, session duration, return visits (no real effect)

Pipeline stages
---------------
1. Power analysis  → required n for 1% absolute MDE at 5% baseline
2. Sequential      → OBF interim at 50% information; expect STOP_WIN
3. Proportion test → primary metric z-test; expect p < 0.01, CI excludes 0
4. CUPED           → revenue variance reduction ≥ 20% with ρ ≈ 0.6 covariate
5. BH correction   → 5-metric FDR control; only the two real effects survive

Data construction
-----------------
Revenue data: pre ~ N(10, 5); post = 0.6 × pre + N(0, 4) + [0.3 if treatment].
This gives E[ρ(pre, post)] = 0.6 and E[variance reduction] ≈ 36%.
Seed 42 is fixed so the suite is deterministic across runs.
"""

from __future__ import annotations

import warnings
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.stats import norm

from app.stats.corrections import apply_multiple_correction, compare_corrections
from app.stats.cuped import apply_cuped, estimate_variance_reduction
from app.stats.power import calculate_power, calculate_sample_size
from app.stats.sequential import (
    compute_obrien_fleming_boundaries,
    evaluate_interim_look,
)
from app.stats.testing import run_proportion_test

# ---------------------------------------------------------------------------
# Scenario constants
# ---------------------------------------------------------------------------

BASELINE_RATE = 0.05  # 5% purchase conversion
MDE = 0.01  # detect 5% → 6% (1 pp absolute)
ALPHA = 0.05
POWER_TARGET = 0.80

N_PER_GROUP = 5_000  # users observed at the interim look
N_PLANNED = 10_000  # per-group target for the full experiment (2-look plan)

# Primary metric — conversions in each group
CONTROL_CONVERSIONS = 250  # 5.0% (= 250 / 5,000)
TREATMENT_CONVERSIONS = 325  # 6.5% (= 325 / 5,000); 1.5× the MDE, well-powered

# Add-to-cart — null metric (noisy, no real effect)
ADD_TO_CART_CTRL = 750  # 15.0%
ADD_TO_CART_TRTMT = 775  # 15.5% (+0.5 pp; not significant)

# Fully synthetic null p-values for the remaining two metrics
P_SESSION_DURATION = 0.12
P_RETURN_VISITS = 0.45


# ---------------------------------------------------------------------------
# Module-scoped fixture — run the full pipeline once, share across all tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pipeline() -> SimpleNamespace:
    """Compute all five pipeline stages and return results as a namespace."""
    rng = np.random.default_rng(42)
    n = N_PER_GROUP

    # ── Stage 1: Power analysis ──────────────────────────────────────────────
    size_result = calculate_sample_size(BASELINE_RATE, MDE, ALPHA, POWER_TARGET)
    achieved_power_at_planned_n = calculate_power(BASELINE_RATE, MDE, N_PLANNED, ALPHA)

    # ── Stage 3: Primary metric proportion test ──────────────────────────────
    # Computed before sequential so the z-stat is available for stage 2.
    prop_result = run_proportion_test(
        CONTROL_CONVERSIONS,
        n,
        TREATMENT_CONVERSIONS,
        n,
        ALPHA,
    )

    # ── Stage 2: Sequential — two-look OBF plan, evaluate at 50% info ────────
    boundaries = compute_obrien_fleming_boundaries(
        total_planned_n=N_PLANNED,
        n_interim_looks=2,
        alpha=ALPHA,
        two_sided=True,
    )
    seq_decision = evaluate_interim_look(
        current_z=prop_result.test_statistic,
        current_n=n,  # 5,000 of 10,000 planned → t = 0.5
        boundaries=boundaries,
    )

    # ── Stage 4: CUPED on revenue metric ────────────────────────────────────
    # pre ~ N(10, 5) for both groups; post = 0.6×pre + N(0,4); treatment +0.3.
    pre_ctrl = rng.normal(10, 5, n)
    pre_trt = rng.normal(10, 5, n)
    pre_all = np.concatenate([pre_ctrl, pre_trt])

    noise = rng.normal(0, 4, 2 * n)
    post_all = 0.6 * pre_all + noise
    post_all[n:] += 0.3  # treatment uplift: +0.3 units on a mean ≈ 10

    assignment = [0] * n + [1] * n

    cuped_result = apply_cuped(pre_all.tolist(), post_all.tolist(), assignment)
    var_reduction_est = estimate_variance_reduction(pre_all.tolist(), post_all.tolist())

    # ── Stage 5: BH correction on 5 metrics ─────────────────────────────────
    add_to_cart_result = run_proportion_test(
        ADD_TO_CART_CTRL,
        n,
        ADD_TO_CART_TRTMT,
        n,
        ALPHA,
    )

    p_values = np.array(
        [
            prop_result.p_value,  # [0] conversion   (significant)
            cuped_result.adjusted_test_result.p_value,  # [1] revenue CUPED (significant)
            add_to_cart_result.p_value,  # [2] add-to-cart   (null)
            P_SESSION_DURATION,  # [3] session dur.  (null)
            P_RETURN_VISITS,  # [4] return visits (null)
        ]
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        bh_result = apply_multiple_correction(p_values, "fdr_bh", ALPHA)
        comparison = compare_corrections(p_values, ALPHA)

    return SimpleNamespace(
        # power
        size_result=size_result,
        achieved_power_at_planned_n=achieved_power_at_planned_n,
        # sequential
        boundaries=boundaries,
        seq_decision=seq_decision,
        # primary metric
        prop_result=prop_result,
        # CUPED
        cuped_result=cuped_result,
        var_reduction_est=var_reduction_est,
        # multi-metric
        add_to_cart_result=add_to_cart_result,
        p_values=p_values,
        bh_result=bh_result,
        comparison=comparison,
    )


# ---------------------------------------------------------------------------
# Stage 1 — Power analysis
# ---------------------------------------------------------------------------


class TestPowerAnalysis:
    def test_required_n_positive(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.size_result.control_size > 0

    def test_required_n_plausible_for_mde(self, pipeline: SimpleNamespace) -> None:
        """For MDE=0.01 at baseline=0.05: Cohen's d ≈ 0.044, n ≈ 8,100.
        Allow a wide window to accommodate both statsmodels and fallback paths."""
        assert 3_000 < pipeline.size_result.control_size < 20_000

    def test_planned_n_achieves_target_power(self, pipeline: SimpleNamespace) -> None:
        """N_PLANNED = 10,000 per group should exceed the 80% power threshold."""
        assert pipeline.achieved_power_at_planned_n >= POWER_TARGET

    def test_power_curve_is_monotone(self, pipeline: SimpleNamespace) -> None:
        powers = [pt["power"] for pt in pipeline.size_result.power_curve]
        assert all(b >= a - 1e-9 for a, b in zip(powers, powers[1:]))

    def test_power_curve_reaches_high_power(self, pipeline: SimpleNamespace) -> None:
        """The rightmost point of the power curve (2× required n) should be > 0.95."""
        assert pipeline.size_result.power_curve[-1]["power"] > 0.95


# ---------------------------------------------------------------------------
# Stage 2 — Sequential / interim analysis
# ---------------------------------------------------------------------------


class TestSequentialAnalysis:
    def test_two_look_plan_has_two_boundaries(self, pipeline: SimpleNamespace) -> None:
        assert len(pipeline.boundaries.z_boundary_per_look) == 2

    def test_interim_boundary_more_conservative_than_final(
        self, pipeline: SimpleNamespace
    ) -> None:
        """OBF property: z*(t=0.5) > z*(t=1.0) — early looks require stronger evidence."""
        z0 = pipeline.boundaries.z_boundary_per_look[0]
        z1 = pipeline.boundaries.z_boundary_per_look[1]
        assert z0 > z1

    def test_interim_boundary_exact_value(self, pipeline: SimpleNamespace) -> None:
        """z*(0.5) = z_crit / √0.5 = norm.ppf(0.975) / √0.5 ≈ 2.772."""
        expected = norm.ppf(0.975) / (0.5**0.5)
        assert pipeline.boundaries.z_boundary_per_look[0] == pytest.approx(
            expected, rel=1e-5
        )

    def test_final_boundary_equals_uncorrected_z(
        self, pipeline: SimpleNamespace
    ) -> None:
        """OBF final look (t=1.0) collapses to the ordinary z critical value."""
        assert pipeline.boundaries.z_boundary_per_look[-1] == pytest.approx(
            norm.ppf(0.975), rel=1e-5
        )

    def test_alpha_budget_sums_to_alpha(self, pipeline: SimpleNamespace) -> None:
        total = sum(pipeline.boundaries.alpha_spent_per_look)
        assert total == pytest.approx(ALPHA, abs=1e-10)

    def test_decision_is_stop_win(self, pipeline: SimpleNamespace) -> None:
        """z ≈ 3.22 exceeds the OBF boundary ≈ 2.77 at 50% information → stop early."""
        assert pipeline.seq_decision.decision == "STOP_WIN"

    def test_info_fraction_is_fifty_percent(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.seq_decision.info_fraction_complete == pytest.approx(0.5)

    def test_sequential_z_comes_from_proportion_test(
        self, pipeline: SimpleNamespace
    ) -> None:
        """The z fed into sequential must equal the proportion test statistic."""
        assert pipeline.seq_decision.current_z == pytest.approx(
            pipeline.prop_result.test_statistic, rel=1e-9
        )


# ---------------------------------------------------------------------------
# Stage 3 — Proportion test (primary metric: conversion)
# ---------------------------------------------------------------------------


class TestProportionTest:
    def test_significant_at_alpha(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.prop_result.p_value < ALPHA

    def test_highly_significant(self, pipeline: SimpleNamespace) -> None:
        """Effect is 1.5× MDE; with n=5,000 the z≈3.22 gives p ≈ 0.0013."""
        assert pipeline.prop_result.p_value < 0.01

    def test_is_significant_flag(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.prop_result.is_significant is True

    def test_ci_lower_bound_positive(self, pipeline: SimpleNamespace) -> None:
        """95% CI on (treatment − control) must be entirely above zero."""
        lo, _ = pipeline.prop_result.confidence_interval
        assert lo > 0.0

    def test_ci_upper_bound_positive(self, pipeline: SimpleNamespace) -> None:
        _, hi = pipeline.prop_result.confidence_interval
        assert hi > 0.0

    def test_positive_absolute_lift(self, pipeline: SimpleNamespace) -> None:
        """Treatment 6.5% > control 5.0% → lift_abs = +0.015."""
        assert pipeline.prop_result.lift_abs == pytest.approx(0.015, abs=1e-9)

    def test_positive_relative_lift(self, pipeline: SimpleNamespace) -> None:
        """Relative lift = 0.015 / 0.05 × 100 = 30%."""
        assert pipeline.prop_result.lift_pct == pytest.approx(30.0, abs=1e-3)

    def test_test_type(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.prop_result.test_type == "z-test"


# ---------------------------------------------------------------------------
# Stage 4 — CUPED variance reduction
# ---------------------------------------------------------------------------


class TestCupedVarianceReduction:
    def test_adjusted_test_is_significant(self, pipeline: SimpleNamespace) -> None:
        """CUPED-adjusted revenue test should detect the 0.3-unit treatment uplift."""
        assert pipeline.cuped_result.adjusted_test_result.is_significant

    def test_unadjusted_test_also_significant(self, pipeline: SimpleNamespace) -> None:
        """With n=5,000 and d≈0.06, the unadjusted Welch t-test should also be p<0.05."""
        assert pipeline.cuped_result.unadjusted_test_result.is_significant

    def test_variance_reduction_exceeds_threshold(
        self, pipeline: SimpleNamespace
    ) -> None:
        """ρ ≈ 0.6 → variance reduction ≈ 36%; empirical value should exceed 20%."""
        assert pipeline.cuped_result.variance_reduction_pct > 20.0

    def test_estimate_and_apply_agree(self, pipeline: SimpleNamespace) -> None:
        """estimate_variance_reduction and apply_cuped measure the same ρ²;
        they should agree within 2 percentage points."""
        diff = abs(
            pipeline.cuped_result.variance_reduction_pct - pipeline.var_reduction_est
        )
        assert diff < 2.0

    def test_adjusted_ci_narrower_than_unadjusted(
        self, pipeline: SimpleNamespace
    ) -> None:
        """CUPED shrinks SE → the adjusted CI is strictly narrower."""
        adj_lo, adj_hi = pipeline.cuped_result.adjusted_test_result.confidence_interval
        unadj_lo, unadj_hi = (
            pipeline.cuped_result.unadjusted_test_result.confidence_interval
        )
        assert (adj_hi - adj_lo) < (unadj_hi - unadj_lo)

    def test_adjusted_z_larger_than_unadjusted(self, pipeline: SimpleNamespace) -> None:
        """Smaller SE → larger |z|; CUPED strictly improves power.
        Compare z-statistics rather than p-values because both can underflow
        to 0.0 at this effect size (n=5,000, d≈0.06 adjusted)."""
        z_adj = abs(pipeline.cuped_result.adjusted_test_result.test_statistic)
        z_unadj = abs(pipeline.cuped_result.unadjusted_test_result.test_statistic)
        assert z_adj > z_unadj

    def test_correlation_is_substantial(self, pipeline: SimpleNamespace) -> None:
        """Constructed with ρ = 0.6; empirical correlation should exceed 0.4 at n=5k."""
        assert pipeline.cuped_result.correlation_pre_post > 0.4

    def test_cuped_preserves_lift(self, pipeline: SimpleNamespace) -> None:
        """CUPED adjustment is unbiased: adjusted lift ≈ raw lift.
        Residual difference is theta × (mean_pre_trt − mean_pre_ctrl) ≈ 0.6 × 0.07 ≈ 0.04.
        """
        ctrl = pipeline.cuped_result.control_summary
        trt = pipeline.cuped_result.treatment_summary
        raw_lift = trt.post_mean - ctrl.post_mean
        adj_lift = trt.adjusted_mean - ctrl.adjusted_mean
        assert abs(raw_lift - adj_lift) < 0.20

    def test_group_sample_sizes(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.cuped_result.control_summary.n_users == N_PER_GROUP
        assert pipeline.cuped_result.treatment_summary.n_users == N_PER_GROUP


# ---------------------------------------------------------------------------
# Stage 5 — Multiple comparison correction (BH on 5 metrics)
# ---------------------------------------------------------------------------


class TestMultiMetricBHCorrection:
    def test_conversion_survives_bh(self, pipeline: SimpleNamespace) -> None:
        """Primary metric p ≈ 0.001 should survive BH at FDR = 0.05."""
        assert pipeline.bh_result.reject_mask[0]

    def test_cuped_revenue_survives_bh(self, pipeline: SimpleNamespace) -> None:
        """CUPED-adjusted revenue p ≈ 0.0002 should survive BH."""
        assert pipeline.bh_result.reject_mask[1]

    def test_add_to_cart_does_not_survive(self, pipeline: SimpleNamespace) -> None:
        """Add-to-cart effect is noise; should not survive BH."""
        assert not pipeline.bh_result.reject_mask[2]

    def test_session_duration_does_not_survive(self, pipeline: SimpleNamespace) -> None:
        assert not pipeline.bh_result.reject_mask[3]

    def test_return_visits_does_not_survive(self, pipeline: SimpleNamespace) -> None:
        assert not pipeline.bh_result.reject_mask[4]

    def test_exactly_two_rejections(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.bh_result.n_rejected == 2

    def test_fdr_upper_bound(self, pipeline: SimpleNamespace) -> None:
        assert pipeline.bh_result.fdr_upper_bound == pytest.approx(ALPHA)

    def test_bonferroni_no_more_powerful_than_bh(
        self, pipeline: SimpleNamespace
    ) -> None:
        """Bonferroni ≤ BH in number of rejections (BH is uniformly more powerful)."""
        assert (
            pipeline.comparison.bonferroni.n_rejected
            <= pipeline.comparison.fdr_bh.n_rejected
        )

    def test_comparison_summary_is_informative(self, pipeline: SimpleNamespace) -> None:
        """Summary should name the most and least powerful methods."""
        summary = pipeline.comparison.summary.lower()
        assert "most powerful" in summary or "all methods agree" in summary

    def test_most_significant_metric_has_smallest_corrected_p(
        self, pipeline: SimpleNamespace
    ) -> None:
        """The index with the smallest original p should also have the smallest q-value."""
        min_orig_idx = int(np.argmin(pipeline.p_values))
        min_corr_idx = int(np.argmin(pipeline.bh_result.corrected_p))
        assert min_orig_idx == min_corr_idx

    def test_corrected_p_array_length(self, pipeline: SimpleNamespace) -> None:
        assert len(pipeline.bh_result.corrected_p) == 5
        assert len(pipeline.bh_result.reject_mask) == 5


# ---------------------------------------------------------------------------
# Cross-stage consistency
# ---------------------------------------------------------------------------


class TestCrossStageConsistency:
    def test_conversion_p_value_is_first_bh_input(
        self, pipeline: SimpleNamespace
    ) -> None:
        """The proportion test p-value must be p_values[0]."""
        assert pipeline.p_values[0] == pytest.approx(pipeline.prop_result.p_value)

    def test_cuped_p_value_is_second_bh_input(self, pipeline: SimpleNamespace) -> None:
        """The CUPED adjusted p-value must be p_values[1]."""
        assert pipeline.p_values[1] == pytest.approx(
            pipeline.cuped_result.adjusted_test_result.p_value
        )

    def test_primary_metric_significant_in_both_test_and_bh(
        self, pipeline: SimpleNamespace
    ) -> None:
        """Conversion is significant in the raw test AND survives multi-metric BH."""
        assert pipeline.prop_result.is_significant
        assert pipeline.bh_result.reject_mask[0]

    def test_stop_win_implies_significant_primary_metric(
        self, pipeline: SimpleNamespace
    ) -> None:
        """If sequential says STOP_WIN, the primary test must also be significant."""
        if pipeline.seq_decision.decision == "STOP_WIN":
            assert pipeline.prop_result.is_significant

    def test_cuped_z_larger_than_unadjusted_in_bh_context(
        self, pipeline: SimpleNamespace
    ) -> None:
        """CUPED-adjusted z (feeds into BH via p_values[1]) exceeds unadjusted z.
        Compared on z-statistics because both p-values can underflow to 0.0."""
        z_adj = abs(pipeline.cuped_result.adjusted_test_result.test_statistic)
        z_unadj = abs(pipeline.cuped_result.unadjusted_test_result.test_statistic)
        assert z_adj > z_unadj

    def test_null_metrics_larger_p_than_real_effects(
        self, pipeline: SimpleNamespace
    ) -> None:
        """All null-metric p-values must exceed both significant metric p-values."""
        p_real = [pipeline.p_values[0], pipeline.p_values[1]]
        p_null = [pipeline.p_values[2], pipeline.p_values[3], pipeline.p_values[4]]
        assert all(pn > pr for pn in p_null for pr in p_real)

    def test_pipeline_overall_conclusion(self, pipeline: SimpleNamespace) -> None:
        """End-to-end: experiment should reach a STOP_WIN with two surviving metrics."""
        assert pipeline.seq_decision.decision == "STOP_WIN"
        assert pipeline.prop_result.is_significant
        assert pipeline.bh_result.n_rejected >= 1

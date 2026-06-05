"""
Unit and integration tests for backend/app/stats/engine.py.

Coverage targets:
  - ExperimentConfig and ExperimentData validation
  - All six pipeline stages individually
  - Overall recommendation logic (RUN / STOP_WIN / STOP_LOSE / NO_EFFECT)
  - Warning collection (imbalance, low events, underpowered)
  - Full end-to-end shopping scenario
"""

from __future__ import annotations

import pytest
import numpy as np

from app.stats.engine import (
    ExperimentAnalysis,
    ExperimentConfig,
    ExperimentData,
    analyze_experiment,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def significant_proportion_data() -> tuple[ExperimentConfig, ExperimentData]:
    """5% control → 7% treatment at n=5000: clearly significant."""
    return (
        ExperimentConfig(test_type="proportion"),
        ExperimentData(
            control_n=5000,
            treatment_n=5000,
            control_success=250,
            treatment_success=350,
        ),
    )


@pytest.fixture()
def insignificant_proportion_data() -> tuple[ExperimentConfig, ExperimentData]:
    """5.0% vs 5.04% — negligible effect, not significant."""
    return (
        ExperimentConfig(test_type="proportion"),
        ExperimentData(
            control_n=5000,
            treatment_n=5000,
            control_success=250,
            treatment_success=252,
        ),
    )


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestExperimentConfig:
    def test_defaults(self) -> None:
        cfg = ExperimentConfig()
        assert cfg.alpha == 0.05
        assert cfg.power == 0.80
        assert cfg.test_type == "proportion"
        assert cfg.sequential_looks == 1
        assert cfg.n_metrics == 1
        assert cfg.has_cuped_data is False
        assert cfg.planned_n_per_group is None

    def test_alpha_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            ExperimentConfig(alpha=0.0)

    def test_alpha_one_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            ExperimentConfig(alpha=1.0)

    def test_alpha_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            ExperimentConfig(alpha=1.5)

    def test_power_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="power"):
            ExperimentConfig(power=0.0)

    def test_power_one_raises(self) -> None:
        with pytest.raises(ValueError, match="power"):
            ExperimentConfig(power=1.0)

    def test_sequential_looks_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="sequential_looks"):
            ExperimentConfig(sequential_looks=0)

    def test_n_metrics_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="n_metrics"):
            ExperimentConfig(n_metrics=0)

    def test_planned_n_per_group_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="planned_n_per_group"):
            ExperimentConfig(planned_n_per_group=0)

    def test_valid_custom_config(self) -> None:
        cfg = ExperimentConfig(
            alpha=0.01,
            power=0.90,
            test_type="mean",
            sequential_looks=5,
            n_metrics=4,
            has_cuped_data=True,
            planned_n_per_group=2000,
        )
        assert cfg.alpha == 0.01
        assert cfg.planned_n_per_group == 2000


# ---------------------------------------------------------------------------
# Data validation
# ---------------------------------------------------------------------------


class TestExperimentData:
    def test_negative_control_n_raises(self) -> None:
        with pytest.raises(ValueError):
            ExperimentData(
                control_n=-1,
                treatment_n=100,
                control_success=5,
                treatment_success=7,
            )

    def test_zero_treatment_n_raises(self) -> None:
        with pytest.raises(ValueError):
            ExperimentData(
                control_n=100,
                treatment_n=0,
                control_success=5,
                treatment_success=7,
            )

    def test_valid_proportion_data(self) -> None:
        d = ExperimentData(
            control_n=100, treatment_n=100, control_success=5, treatment_success=7
        )
        assert d.control_n == 100
        assert d.cuped_covariates is None

    def test_valid_mean_data(self) -> None:
        d = ExperimentData(
            control_n=50,
            treatment_n=50,
            control_success=[1.0, 2.0] * 25,
            treatment_success=[1.5, 2.5] * 25,
        )
        assert isinstance(d.control_success, list)


# ---------------------------------------------------------------------------
# Proportion pipeline
# ---------------------------------------------------------------------------


class TestProportionPipeline:
    def test_significant_effect_is_stop_win(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "STOP_WIN"
        assert result.primary_result.is_significant
        assert result.primary_result.test_type == "z-test"

    def test_no_sequential_when_single_look(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.sequential_status is None

    def test_no_cuped_when_not_configured(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.cuped_result is None

    def test_no_corrections_for_single_metric(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.corrected_results is None

    def test_plain_english_nonempty(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert len(result.plain_english) > 20

    def test_required_sample_size_populated(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.required_sample_size.total_sample_size > 0
        assert result.required_sample_size.cohens_d > 0

    def test_insignificant_at_planned_n_is_no_effect(
        self, insignificant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = insignificant_proportion_data
        # Explicitly provide planned_n equal to current n so engine knows we're done.
        cfg = ExperimentConfig(test_type="proportion", planned_n_per_group=5000)
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "NO_EFFECT"
        assert not result.primary_result.is_significant

    def test_underpowered_is_run(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=50,
            treatment_n=50,
            control_success=2,
            treatment_success=3,
        )
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "RUN"
        assert not result.primary_result.is_significant

    def test_zero_zero_conversions_does_not_crash(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=0,
            treatment_success=0,
        )
        result = analyze_experiment(cfg, data)
        assert isinstance(result, ExperimentAnalysis)
        assert not result.primary_result.is_significant

    def test_proportion_ci_excludes_zero_when_significant(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        lo, hi = result.primary_result.confidence_interval
        assert lo > 0, "lower CI bound should be above 0 for positive, significant lift"

    def test_lift_pct_positive_when_treatment_higher(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.primary_result.lift_pct > 0


# ---------------------------------------------------------------------------
# Mean / ratio pipeline
# ---------------------------------------------------------------------------


class TestMeanPipeline:
    def test_significant_mean_effect_is_stop_win(self) -> None:
        rng = np.random.default_rng(42)
        ctrl = rng.normal(10.0, 3.0, 500).tolist()
        trt = (rng.normal(10.0, 3.0, 500) + 1.5).tolist()
        cfg = ExperimentConfig(test_type="mean")
        data = ExperimentData(
            control_n=500,
            treatment_n=500,
            control_success=ctrl,
            treatment_success=trt,
        )
        result = analyze_experiment(cfg, data)
        assert result.primary_result.test_type == "t-test"
        assert result.primary_result.is_significant
        assert result.overall_recommendation == "STOP_WIN"

    def test_null_mean_effect_not_significant(self) -> None:
        rng = np.random.default_rng(99)
        ctrl = rng.normal(10.0, 3.0, 100).tolist()
        trt = rng.normal(10.0, 3.0, 100).tolist()
        cfg = ExperimentConfig(test_type="mean")
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=ctrl,
            treatment_success=trt,
        )
        result = analyze_experiment(cfg, data)
        assert result.primary_result.test_type == "t-test"
        assert not result.primary_result.is_significant

    def test_mean_required_sample_size_uses_cohens_d_method(self) -> None:
        rng = np.random.default_rng(7)
        ctrl = rng.normal(10.0, 2.0, 200).tolist()
        trt = (rng.normal(10.0, 2.0, 200) + 0.5).tolist()
        cfg = ExperimentConfig(test_type="mean")
        data = ExperimentData(
            control_n=200,
            treatment_n=200,
            control_success=ctrl,
            treatment_success=trt,
        )
        result = analyze_experiment(cfg, data)
        assert result.required_sample_size.method_used == "engine_cohens_d_wald"
        assert result.required_sample_size.total_sample_size > 0

    def test_ratio_test_type_uses_t_test(self) -> None:
        rng = np.random.default_rng(11)
        ctrl = rng.exponential(5.0, 300).tolist()
        trt = rng.exponential(5.5, 300).tolist()
        cfg = ExperimentConfig(test_type="ratio")
        data = ExperimentData(
            control_n=300,
            treatment_n=300,
            control_success=ctrl,
            treatment_success=trt,
        )
        result = analyze_experiment(cfg, data)
        assert result.primary_result.test_type == "t-test"


# ---------------------------------------------------------------------------
# Sequential analysis
# ---------------------------------------------------------------------------


class TestSequentialPipeline:
    def test_no_sequential_when_sequential_looks_eq_1(self) -> None:
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=1)
        data = ExperimentData(
            control_n=1000,
            treatment_n=1000,
            control_success=50,
            treatment_success=70,
        )
        result = analyze_experiment(cfg, data)
        assert result.sequential_status is None

    def test_sequential_status_populated_when_looks_gt_1(self) -> None:
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=3)
        data = ExperimentData(
            control_n=2000,
            treatment_n=2000,
            control_success=100,
            treatment_success=120,
        )
        result = analyze_experiment(cfg, data, current_look=None)
        assert result.sequential_status is not None
        assert result.sequential_status.decision in (
            "CONTINUE",
            "STOP_WIN",
            "STOP_LOSE",
        )

    def test_sequential_stop_win_at_interim(self) -> None:
        # 5% vs 10% at look 2/4 (t=0.5): z ≈ 4.24, OBF boundary ≈ 2.77 → STOP_WIN
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=4)
        data = ExperimentData(
            control_n=1000,
            treatment_n=1000,
            control_success=50,
            treatment_success=100,
        )
        result = analyze_experiment(cfg, data, current_look=2)
        assert result.sequential_status is not None
        assert result.sequential_status.decision == "STOP_WIN"
        assert result.overall_recommendation == "STOP_WIN"

    def test_sequential_continue_returns_run(self) -> None:
        # 10% vs 11% at look 1/4 (t=0.25): |z| ≈ 0.73
        # OBF efficacy boundary ≈ 3.92, futility ≈ 0.56 → inside both → CONTINUE
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=4)
        data = ExperimentData(
            control_n=1000,
            treatment_n=1000,
            control_success=100,
            treatment_success=110,
        )
        result = analyze_experiment(cfg, data, current_look=1)
        assert result.sequential_status is not None
        assert result.sequential_status.decision == "CONTINUE"
        assert result.overall_recommendation == "RUN"

    def test_sequential_info_fraction_in_01(self) -> None:
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=5)
        data = ExperimentData(
            control_n=500,
            treatment_n=500,
            control_success=25,
            treatment_success=30,
        )
        result = analyze_experiment(cfg, data, current_look=2)
        assert result.sequential_status is not None
        assert 0.0 < result.sequential_status.info_fraction_complete <= 1.0

    def test_sequential_required_z_decreases_towards_final_look(self) -> None:
        # At earlier looks the O'Brien-Fleming boundary should be higher.
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=4)
        data_early = ExperimentData(
            control_n=500, treatment_n=500, control_success=25, treatment_success=28
        )
        data_late = ExperimentData(
            control_n=1500, treatment_n=1500, control_success=75, treatment_success=84
        )
        early = analyze_experiment(cfg, data_early, current_look=1)
        late = analyze_experiment(cfg, data_late, current_look=3)
        assert early.sequential_status is not None
        assert late.sequential_status is not None
        assert early.sequential_status.required_z > late.sequential_status.required_z


# ---------------------------------------------------------------------------
# CUPED pipeline
# ---------------------------------------------------------------------------


class TestCupedPipeline:
    def test_cuped_none_when_has_cuped_data_false(self) -> None:
        rng = np.random.default_rng(1)
        n = 200
        cfg = ExperimentConfig(test_type="mean", has_cuped_data=False)
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=rng.normal(10, 2, n).tolist(),
            treatment_success=rng.normal(10.5, 2, n).tolist(),
        )
        result = analyze_experiment(cfg, data)
        assert result.cuped_result is None

    def test_cuped_none_when_covariates_missing(self) -> None:
        rng = np.random.default_rng(2)
        n = 200
        cfg = ExperimentConfig(test_type="mean", has_cuped_data=True)
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=rng.normal(10, 2, n).tolist(),
            treatment_success=rng.normal(10.5, 2, n).tolist(),
            cuped_covariates=None,  # missing despite flag
        )
        result = analyze_experiment(cfg, data)
        assert result.cuped_result is None

    def test_cuped_populated_for_mean_test(self) -> None:
        rng = np.random.default_rng(42)
        n = 500
        pre = rng.normal(10, 5, 2 * n)
        post = 0.6 * pre + rng.normal(0, 4, 2 * n)
        post[n:] += 0.3  # treatment lift
        cfg = ExperimentConfig(test_type="mean", has_cuped_data=True)
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=post[:n].tolist(),
            treatment_success=post[n:].tolist(),
            cuped_covariates=pre.tolist(),
        )
        result = analyze_experiment(cfg, data)
        assert result.cuped_result is not None
        assert result.cuped_result.variance_reduction_pct > 0.0
        assert result.cuped_result.theta != 0.0

    def test_cuped_populated_for_proportion_test(self) -> None:
        rng = np.random.default_rng(55)
        n = 1000
        pre = rng.binomial(1, 0.3, 2 * n).astype(float).tolist()
        cfg = ExperimentConfig(test_type="proportion", has_cuped_data=True)
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=80,
            treatment_success=100,
            cuped_covariates=pre,
        )
        result = analyze_experiment(cfg, data)
        assert result.cuped_result is not None

    def test_cuped_skipped_when_covariate_length_wrong(self) -> None:
        rng = np.random.default_rng(3)
        n = 200
        cfg = ExperimentConfig(test_type="mean", has_cuped_data=True)
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=rng.normal(10, 2, n).tolist(),
            treatment_success=rng.normal(10.5, 2, n).tolist(),
            cuped_covariates=rng.normal(10, 2, n).tolist(),  # length=n, not 2n
        )
        result = analyze_experiment(cfg, data)
        # Wrong length → CUPED silently skipped.
        assert result.cuped_result is None


# ---------------------------------------------------------------------------
# Multiple comparison corrections
# ---------------------------------------------------------------------------


class TestCorrectionsPipeline:
    def test_corrections_none_for_single_metric(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.corrected_results is None

    def test_corrections_applied_for_multiple_metrics(self) -> None:
        cfg = ExperimentConfig(test_type="proportion", n_metrics=3)
        data = ExperimentData(
            control_n=5000,
            treatment_n=5000,
            control_success=250,
            treatment_success=350,
        )
        result = analyze_experiment(cfg, data)
        assert result.corrected_results is not None
        assert result.corrected_results.method == "fdr_bh"
        assert len(result.corrected_results.original_p) == 1

    def test_corrections_with_cuped_has_two_p_values(self) -> None:
        rng = np.random.default_rng(42)
        n = 500
        pre = rng.normal(10, 5, 2 * n)
        post = 0.6 * pre + rng.normal(0, 4, 2 * n)
        post[n:] += 0.3
        cfg = ExperimentConfig(test_type="mean", n_metrics=2, has_cuped_data=True)
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=post[:n].tolist(),
            treatment_success=post[n:].tolist(),
            cuped_covariates=pre.tolist(),
        )
        result = analyze_experiment(cfg, data)
        assert result.corrected_results is not None
        assert len(result.corrected_results.original_p) == 2

    def test_corrections_reject_mask_shape(self) -> None:
        cfg = ExperimentConfig(test_type="proportion", n_metrics=5)
        data = ExperimentData(
            control_n=5000,
            treatment_n=5000,
            control_success=250,
            treatment_success=325,
        )
        result = analyze_experiment(cfg, data)
        assert result.corrected_results is not None
        assert result.corrected_results.reject_mask.shape == (1,)


# ---------------------------------------------------------------------------
# Recommendation logic
# ---------------------------------------------------------------------------


class TestRecommendationLogic:
    def test_significant_result_is_stop_win(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "STOP_WIN"

    def test_no_effect_when_planned_n_reached(
        self, insignificant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        _cfg, data = insignificant_proportion_data
        cfg = ExperimentConfig(test_type="proportion", planned_n_per_group=5000)
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "NO_EFFECT"

    def test_run_when_below_planned_n(self) -> None:
        cfg = ExperimentConfig(test_type="proportion", planned_n_per_group=10000)
        data = ExperimentData(
            control_n=1000,
            treatment_n=1000,
            control_success=50,
            treatment_success=52,
        )
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "RUN"
        assert not result.primary_result.is_significant

    def test_run_when_tiny_sample(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=10,
            treatment_n=10,
            control_success=1,
            treatment_success=1,
        )
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation == "RUN"

    def test_stop_lose_from_sequential(self) -> None:
        # Tiny effect at first of 4 looks → futility boundary crossed.
        cfg = ExperimentConfig(test_type="proportion", sequential_looks=4)
        data = ExperimentData(
            control_n=1000,
            treatment_n=1000,
            control_success=50,
            treatment_success=50,  # z=0, below futility
        )
        result = analyze_experiment(cfg, data, current_look=1)
        assert result.sequential_status is not None
        assert result.sequential_status.decision == "STOP_LOSE"
        assert result.overall_recommendation == "STOP_LOSE"

    def test_recommendation_field_is_valid_literal(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert result.overall_recommendation in (
            "RUN",
            "STOP_WIN",
            "STOP_LOSE",
            "NO_EFFECT",
        )


# ---------------------------------------------------------------------------
# Warning collection
# ---------------------------------------------------------------------------


class TestWarnings:
    def test_imbalance_warning_when_ratio_exceeds_threshold(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=1000,
            treatment_n=800,  # 200/1000 = 20% → above 10%
            control_success=50,
            treatment_success=40,
        )
        result = analyze_experiment(cfg, data)
        assert any("imbalance" in w.lower() for w in result.warnings)

    def test_no_imbalance_warning_at_exact_10pct(self) -> None:
        # (1000-900)/1000 = 10.0% → NOT strictly > 10% → no warning.
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=1000,
            treatment_n=900,
            control_success=50,
            treatment_success=45,
        )
        result = analyze_experiment(cfg, data)
        assert not any("imbalance" in w.lower() for w in result.warnings)

    def test_low_events_warning_triggered(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=1000,
            treatment_n=1000,
            control_success=2,
            treatment_success=3,
        )
        result = analyze_experiment(cfg, data)
        assert any("low event" in w.lower() for w in result.warnings)

    def test_no_low_events_warning_when_events_sufficient(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert not any("low event" in w.lower() for w in result.warnings)

    def test_underpowered_warning_when_n_below_required(self) -> None:
        # Very small sample for a moderately-sized target effect.
        cfg = ExperimentConfig(test_type="proportion", planned_n_per_group=5000)
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=5,
            treatment_success=6,
        )
        result = analyze_experiment(cfg, data)
        assert any("underpowered" in w.lower() for w in result.warnings)

    def test_no_duplicate_warnings(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=1000,
            treatment_n=500,  # imbalanced
            control_success=2,
            treatment_success=1,  # low events too
        )
        result = analyze_experiment(cfg, data)
        assert len(result.warnings) == len(set(result.warnings))

    def test_warnings_is_list(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert isinstance(result.warnings, list)


# ---------------------------------------------------------------------------
# Type validation (wrong success type for test_type)
# ---------------------------------------------------------------------------


class TestTypeValidation:
    def test_proportion_with_list_control_raises(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=[0.05] * 100,
            treatment_success=7,
        )
        with pytest.raises(ValueError, match="must be int"):
            analyze_experiment(cfg, data)

    def test_proportion_with_list_treatment_raises(self) -> None:
        cfg = ExperimentConfig(test_type="proportion")
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=5,
            treatment_success=[0.07] * 100,
        )
        with pytest.raises(ValueError, match="must be int"):
            analyze_experiment(cfg, data)

    def test_mean_with_int_control_raises(self) -> None:
        cfg = ExperimentConfig(test_type="mean")
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=5,
            treatment_success=[10.0] * 100,
        )
        with pytest.raises(ValueError, match="must be list"):
            analyze_experiment(cfg, data)

    def test_mean_with_int_treatment_raises(self) -> None:
        cfg = ExperimentConfig(test_type="mean")
        data = ExperimentData(
            control_n=100,
            treatment_n=100,
            control_success=[10.0] * 100,
            treatment_success=7,
        )
        with pytest.raises(ValueError, match="must be list"):
            analyze_experiment(cfg, data)


# ---------------------------------------------------------------------------
# ExperimentAnalysis structure
# ---------------------------------------------------------------------------


class TestAnalysisStructure:
    def test_result_is_experiment_analysis_instance(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert isinstance(result, ExperimentAnalysis)

    def test_p_value_in_01(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert 0.0 <= result.primary_result.p_value <= 1.0

    def test_ci_is_tuple_of_two_floats(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        lo, hi = result.primary_result.confidence_interval
        assert isinstance(lo, float) and isinstance(hi, float)
        assert lo < hi

    def test_power_curve_has_20_points(
        self, significant_proportion_data: tuple[ExperimentConfig, ExperimentData]
    ) -> None:
        cfg, data = significant_proportion_data
        result = analyze_experiment(cfg, data)
        assert len(result.required_sample_size.power_curve) == 20

    def test_mean_engine_power_curve_has_10_points(self) -> None:
        rng = np.random.default_rng(5)
        n = 100
        cfg = ExperimentConfig(test_type="mean")
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=rng.normal(10, 2, n).tolist(),
            treatment_success=rng.normal(10.5, 2, n).tolist(),
        )
        result = analyze_experiment(cfg, data)
        assert len(result.required_sample_size.power_curve) == 10


# ---------------------------------------------------------------------------
# Full integration — shopping scenario
# ---------------------------------------------------------------------------


class TestFullIntegration:
    def test_shopping_conversion_full_pipeline(self) -> None:
        """End-to-end: proportion + sequential + CUPED + corrections."""
        rng = np.random.default_rng(42)
        n = 5000

        # Synthetic pre-period revenue for CUPED covariate.
        pre = rng.normal(10.0, 5.0, 2 * n).tolist()

        cfg = ExperimentConfig(
            alpha=0.05,
            power=0.80,
            test_type="proportion",
            sequential_looks=2,
            n_metrics=3,
            has_cuped_data=True,
        )
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=250,  # 5.0%
            treatment_success=325,  # 6.5%
            cuped_covariates=pre,
        )

        result = analyze_experiment(cfg, data)

        # All stages must produce results.
        assert isinstance(result.primary_result.p_value, float)
        assert 0.0 <= result.primary_result.p_value <= 1.0
        assert result.sequential_status is not None
        assert result.sequential_status.decision in (
            "CONTINUE",
            "STOP_WIN",
            "STOP_LOSE",
        )
        assert result.cuped_result is not None
        assert result.corrected_results is not None
        assert result.corrected_results.method == "fdr_bh"
        assert result.overall_recommendation in (
            "RUN",
            "STOP_WIN",
            "STOP_LOSE",
            "NO_EFFECT",
        )
        assert len(result.plain_english) > 0
        assert isinstance(result.warnings, list)

    def test_null_experiment_full_pipeline(self) -> None:
        """Pipeline handles all-null data without crashing."""
        rng = np.random.default_rng(7)
        n = 500
        pre = rng.normal(10.0, 3.0, 2 * n).tolist()

        cfg = ExperimentConfig(
            test_type="proportion",
            sequential_looks=3,
            n_metrics=2,
            has_cuped_data=True,
            planned_n_per_group=5000,
        )
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=25,  # 5%
            treatment_success=25,  # 5% — no effect
            cuped_covariates=pre,
        )

        result = analyze_experiment(cfg, data)
        assert not result.primary_result.is_significant
        assert result.overall_recommendation in (
            "RUN",
            "STOP_WIN",
            "STOP_LOSE",
            "NO_EFFECT",
        )

    def test_mean_pipeline_with_cuped_and_corrections(self) -> None:
        """Mean test + CUPED + 2-metric correction end-to-end."""
        rng = np.random.default_rng(123)
        n = 800
        pre = rng.normal(50, 10, 2 * n)
        post = 0.7 * pre + rng.normal(0, 7, 2 * n)
        post[n:] += 2.0  # treatment effect

        cfg = ExperimentConfig(
            test_type="mean",
            n_metrics=2,
            has_cuped_data=True,
        )
        data = ExperimentData(
            control_n=n,
            treatment_n=n,
            control_success=post[:n].tolist(),
            treatment_success=post[n:].tolist(),
            cuped_covariates=pre.tolist(),
        )

        result = analyze_experiment(cfg, data)
        assert result.cuped_result is not None
        assert result.corrected_results is not None
        assert len(result.corrected_results.original_p) == 2
        assert result.overall_recommendation in (
            "RUN",
            "STOP_WIN",
            "STOP_LOSE",
            "NO_EFFECT",
        )

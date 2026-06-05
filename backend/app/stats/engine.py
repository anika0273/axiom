"""
Production orchestrator for the Axiom stats pipeline.

``analyze_experiment`` is the single entry point for a full-pipeline analysis.
It chains five stages in order:

    1. Power analysis      → required sample size (SampleSizeResult)
    2. Hypothesis test     → primary result (TestResult)
    3. Sequential check    → optional O'Brien-Fleming decision (SequentialDecision)
    4. CUPED adjustment    → optional variance-reduced result (CUPEDResult)
    5. MCC correction      → optional BH-corrected result (CorrectionResult)
    6. Recommendation      → overall_recommendation + plain_english summary

All stages are independently fallible: an unavailable covariate silently skips
CUPED; a single-metric experiment skips corrections.  No stage blocks another.
"""

from __future__ import annotations

import logging
import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator
from scipy.stats import norm as scipy_norm

from app.stats.corrections import CorrectionResult, apply_multiple_correction
from app.stats.cuped import CUPEDResult, apply_cuped
from app.stats.power import SampleSizeResult, calculate_sample_size
from app.stats.sequential import (
    SequentialDecision,
    compute_obrien_fleming_boundaries,
    evaluate_interim_look,
)
from app.stats.testing import TestResult, run_mean_test, run_proportion_test

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_IMBALANCE_THRESHOLD: float = 0.10  # fraction of larger group
_LOW_EVENTS_THRESHOLD: int = 5  # minimum events per arm


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ExperimentConfig(BaseModel):
    """Pipeline configuration for a single analysis run.

    Args:
        alpha: Two-tailed significance level.  Default 0.05.
        power: Desired statistical power for the sample-size calculation.  Default 0.80.
        test_type: Which hypothesis test to run.
        sequential_looks: Total number of planned looks (including the final).
                          1 = fixed-horizon (no sequential adjustment).
        n_metrics: Number of metrics being tested simultaneously.
                   > 1 triggers BH multiple comparison correction.
        has_cuped_data: Whether ``ExperimentData.cuped_covariates`` will be provided.
        planned_n_per_group: Pre-specified per-group sample size (used to determine
                              NO_EFFECT vs RUN when the test is not significant).
                              If None the required n is inferred from observed data.
    """

    alpha: float = 0.05
    power: float = 0.80
    test_type: Literal["proportion", "mean", "ratio"] = "proportion"
    sequential_looks: int = 1
    n_metrics: int = 1
    has_cuped_data: bool = False
    planned_n_per_group: int | None = None

    @field_validator("alpha")
    @classmethod
    def _alpha_range(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {v}")
        return v

    @field_validator("power")
    @classmethod
    def _power_range(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError(f"power must be in (0, 1), got {v}")
        return v

    @field_validator("sequential_looks")
    @classmethod
    def _sequential_looks_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"sequential_looks must be >= 1, got {v}")
        return v

    @field_validator("n_metrics")
    @classmethod
    def _n_metrics_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"n_metrics must be >= 1, got {v}")
        return v

    @field_validator("planned_n_per_group")
    @classmethod
    def _planned_n_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError(f"planned_n_per_group must be positive, got {v}")
        return v


class ExperimentData(BaseModel):
    """Observed data for a single analysis run.

    Args:
        control_n: Number of subjects in the control group.
        treatment_n: Number of subjects in the treatment group.
        control_success: Successes in control.  ``int`` for proportion tests;
                         ``list[float]`` for mean/ratio tests (per-user values).
        treatment_success: Successes in treatment.  Same type convention.
        cuped_covariates: Pre-experiment per-user covariate for all subjects,
                          control first then treatment (length = control_n + treatment_n).
                          Required only when ``ExperimentConfig.has_cuped_data`` is True.
    """

    control_n: int
    treatment_n: int
    control_success: int | list[float]
    treatment_success: int | list[float]
    cuped_covariates: list[float] | None = None

    @field_validator("control_n", "treatment_n")
    @classmethod
    def _n_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"Group size must be positive, got {v}")
        return v


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


class ExperimentAnalysis(BaseModel):
    """Complete result of a full-pipeline experiment analysis.

    Fields
    ------
    required_sample_size  : Power-analysis output — how large the experiment
                            needs to be to detect the observed (or planned) effect.
    sequential_status     : O'Brien-Fleming decision at the current look.
                            None when sequential_looks == 1.
    primary_result        : Result of the primary hypothesis test.
    cuped_result          : CUPED-adjusted result.  None when unavailable.
    corrected_results     : BH-corrected p-values.  None when n_metrics == 1.
    overall_recommendation: One of RUN / STOP_WIN / STOP_LOSE / NO_EFFECT.
    plain_english         : Human-readable summary suitable for a dashboard.
    warnings              : Non-fatal data-quality or design issues.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    required_sample_size: SampleSizeResult
    sequential_status: SequentialDecision | None
    primary_result: TestResult
    cuped_result: CUPEDResult | None
    corrected_results: CorrectionResult | None
    overall_recommendation: Literal["RUN", "STOP_WIN", "STOP_LOSE", "NO_EFFECT"]
    plain_english: str
    warnings: list[str]


# ---------------------------------------------------------------------------
# Private — stage implementations
# ---------------------------------------------------------------------------


def _power_analysis_proportion(
    control_success: int,
    control_n: int,
    treatment_success: int,
    treatment_n: int,
    alpha: float,
    power: float,
) -> SampleSizeResult:
    """Compute required n from observed proportions."""
    baseline = control_success / control_n
    observed = treatment_success / treatment_n
    mde = observed - baseline

    # Guard degenerate inputs.
    baseline = max(1e-4, min(1.0 - 1e-4, baseline))
    if abs(mde) < 1e-9:
        mde = 1e-4
    treatment = baseline + mde
    if not 0.0 < treatment < 1.0:
        mde = (0.5 - baseline) * 0.1

    return calculate_sample_size(baseline, mde, alpha, power)


def _power_analysis_means(
    control_values: np.ndarray,
    treatment_values: np.ndarray,
    alpha: float,
    power_target: float,
) -> SampleSizeResult:
    """Compute required n for a continuous metric via Cohen's d."""
    mean_c = float(np.mean(control_values))
    mean_t = float(np.mean(treatment_values))
    std_c = float(np.std(control_values, ddof=1))
    std_t = float(np.std(treatment_values, ddof=1))

    pooled_std = math.sqrt((std_c**2 + std_t**2) / 2.0)
    if pooled_std == 0.0:
        pooled_std = 1.0

    d = abs(mean_t - mean_c) / pooled_std
    if d < 1e-9:
        d = 1e-4

    z_a = float(scipy_norm.ppf(1.0 - alpha / 2.0))
    z_b = float(scipy_norm.ppf(power_target))
    n_per = max(1, math.ceil(((z_a + z_b) / d) ** 2))

    curve: list[dict[str, float]] = []
    for mult in np.linspace(0.5, 2.0, 10):
        ni = max(1, int(round(n_per * mult)))
        nc = d * math.sqrt(ni / 2.0)
        pwr = float(
            np.clip(scipy_norm.cdf(nc - z_a) + scipy_norm.cdf(-nc - z_a), 0.0, 1.0)
        )
        curve.append({"n": float(ni), "power": round(pwr, 4)})

    return SampleSizeResult(
        control_size=n_per,
        treatment_size=n_per,
        total_sample_size=2 * n_per,
        cohens_d=round(d, 6),
        method_used="engine_cohens_d_wald",
        power_curve=curve,
    )


def _run_hypothesis_test(config: ExperimentConfig, data: ExperimentData) -> TestResult:
    """Dispatch to the correct test based on test_type."""
    if config.test_type == "proportion":
        if not isinstance(data.control_success, int):
            raise ValueError(
                "control_success must be int for test_type='proportion', "
                f"got {type(data.control_success).__name__}"
            )
        if not isinstance(data.treatment_success, int):
            raise ValueError(
                "treatment_success must be int for test_type='proportion', "
                f"got {type(data.treatment_success).__name__}"
            )
        return run_proportion_test(
            data.control_success,
            data.control_n,
            data.treatment_success,
            data.treatment_n,
            config.alpha,
        )

    # mean or ratio — both use Welch's t-test on per-user arrays
    if not isinstance(data.control_success, list):
        raise ValueError(
            "control_success must be list[float] for test_type='mean'/'ratio', "
            f"got {type(data.control_success).__name__}"
        )
    if not isinstance(data.treatment_success, list):
        raise ValueError(
            "treatment_success must be list[float] for test_type='mean'/'ratio', "
            f"got {type(data.treatment_success).__name__}"
        )
    return run_mean_test(
        np.asarray(data.control_success, dtype=float),
        np.asarray(data.treatment_success, dtype=float),
        config.alpha,
    )


def _run_sequential(
    config: ExperimentConfig,
    data: ExperimentData,
    primary_result: TestResult,
    required_sample_size: SampleSizeResult,
    current_look: int | None,
) -> SequentialDecision | None:
    """Evaluate the O'Brien-Fleming boundary at the current look."""
    if config.sequential_looks <= 1:
        return None

    current_n = data.control_n

    # Estimate planned per-group n: extrapolate from look position if known,
    # otherwise fall back to the power-analysis required n.
    if current_look is not None and current_look > 0:
        planned_n = max(
            current_n, int(current_n * config.sequential_looks / current_look)
        )
    else:
        planned_n = max(current_n, required_sample_size.control_size)

    boundaries = compute_obrien_fleming_boundaries(
        total_planned_n=planned_n,
        n_interim_looks=config.sequential_looks,
        alpha=config.alpha,
        two_sided=True,
    )
    return evaluate_interim_look(
        current_z=primary_result.test_statistic,
        current_n=current_n,
        boundaries=boundaries,
    )


def _run_cuped(
    config: ExperimentConfig,
    data: ExperimentData,
) -> CUPEDResult | None:
    """Apply CUPED if covariates are available and config enables it."""
    if not config.has_cuped_data or data.cuped_covariates is None:
        return None

    total_n = data.control_n + data.treatment_n
    if len(data.cuped_covariates) != total_n:
        logger.warning(
            "cuped_covariates length %d != control_n + treatment_n %d; skipping CUPED",
            len(data.cuped_covariates),
            total_n,
        )
        return None

    # Build per-user outcome arrays.
    if config.test_type == "proportion":
        if not isinstance(data.control_success, int) or not isinstance(
            data.treatment_success, int
        ):
            return None
        y_ctrl: list[float] = [1.0] * data.control_success + [0.0] * (
            data.control_n - data.control_success
        )
        y_trt: list[float] = [1.0] * data.treatment_success + [0.0] * (
            data.treatment_n - data.treatment_success
        )
    else:
        if not isinstance(data.control_success, list) or not isinstance(
            data.treatment_success, list
        ):
            return None
        y_ctrl = list(data.control_success)
        y_trt = list(data.treatment_success)

    post_all = y_ctrl + y_trt
    assignment = [0] * data.control_n + [1] * data.treatment_n

    return apply_cuped(
        pre_experiment_metric=data.cuped_covariates,
        experiment_metric=post_all,
        treatment_assignment=assignment,
    )


def _run_corrections(
    config: ExperimentConfig,
    primary_result: TestResult,
    cuped_result: CUPEDResult | None,
) -> CorrectionResult | None:
    """Apply BH correction when n_metrics > 1."""
    if config.n_metrics <= 1:
        return None

    p_values = [primary_result.p_value]
    if cuped_result is not None:
        p_values.append(cuped_result.adjusted_test_result.p_value)

    return apply_multiple_correction(
        np.array(p_values),
        method="fdr_bh",
        alpha=config.alpha,
    )


def _build_recommendation(
    config: ExperimentConfig,
    data: ExperimentData,
    primary_result: TestResult,
    sequential_status: SequentialDecision | None,
    corrected_results: CorrectionResult | None,
    required_sample_size: SampleSizeResult,
) -> tuple[Literal["RUN", "STOP_WIN", "STOP_LOSE", "NO_EFFECT"], str]:
    """Produce the overall recommendation and a plain-English summary."""
    # Determine significance after corrections when available.
    is_significant: bool
    if corrected_results is not None:
        is_significant = bool(corrected_results.reject_mask[0])
    else:
        is_significant = primary_result.is_significant

    # Sequential decisions override fixed-horizon logic.
    rec: Literal["RUN", "STOP_WIN", "STOP_LOSE", "NO_EFFECT"]
    if sequential_status is not None:
        if sequential_status.decision == "STOP_WIN":
            rec = "STOP_WIN"
        elif sequential_status.decision == "STOP_LOSE":
            rec = "STOP_LOSE"
        else:
            rec = "RUN"
    else:
        # Fixed-horizon: decide based on significance and collected vs planned n.
        current_total = data.control_n + data.treatment_n
        reference_n = (
            config.planned_n_per_group * 2
            if config.planned_n_per_group is not None
            else required_sample_size.total_sample_size
        )
        if is_significant:
            rec = "STOP_WIN"
        elif current_total >= reference_n:
            rec = "NO_EFFECT"
        else:
            rec = "RUN"

    # Build human-readable summary.
    direction = "improved" if primary_result.lift_pct > 0 else "degraded"
    if rec == "STOP_WIN":
        plain = (
            f"The experiment has a winner. Treatment {direction} by "
            f"{abs(primary_result.lift_pct):.1f}% relative "
            f"({primary_result.lift_abs:+.4f} absolute). "
            f"{primary_result.interpretation}"
        )
    elif rec == "STOP_LOSE":
        seq_msg = (
            sequential_status.interpretation
            if sequential_status
            else "Insufficient power."
        )
        plain = f"Stop for futility. {seq_msg}"
    elif rec == "RUN":
        current_total = data.control_n + data.treatment_n
        planned_total = (
            config.planned_n_per_group * 2
            if config.planned_n_per_group is not None
            else required_sample_size.total_sample_size
        )
        seq_msg = f" {sequential_status.interpretation}" if sequential_status else ""
        plain = (
            f"Continue the experiment.{seq_msg} "
            f"Current n={current_total:,} vs required n={planned_total:,}."
        )
    else:  # NO_EFFECT
        plain = (
            f"No statistically significant effect detected "
            f"(p={primary_result.p_value:.3f}, α={config.alpha}). "
            f"The experiment reached its planned sample size. "
            f"Observed lift: {primary_result.lift_pct:+.1f}% "
            f"({primary_result.lift_abs:+.4f} absolute) — "
            f"consider whether this magnitude is practically meaningful."
        )

    return rec, plain


def _collect_warnings(
    config: ExperimentConfig,
    data: ExperimentData,
    primary_result: TestResult,
    required_sample_size: SampleSizeResult,
) -> list[str]:
    """Gather data-quality and design warnings."""
    seen: set[str] = set()
    result: list[str] = []

    def add(w: str) -> None:
        if w not in seen:
            seen.add(w)
            result.append(w)

    # Warnings from the test itself (e.g. small sample, low conversions).
    for w in primary_result.sample_warnings:
        add(w)

    # Group imbalance.
    larger = max(data.control_n, data.treatment_n)
    smaller = min(data.control_n, data.treatment_n)
    if larger > 0 and (larger - smaller) / larger > _IMBALANCE_THRESHOLD:
        ratio = data.control_n / data.treatment_n
        add(
            f"Group imbalance detected: control_n={data.control_n}, "
            f"treatment_n={data.treatment_n} (ratio {ratio:.2f}). "
            "Results may have reduced power."
        )

    # Low event counts for proportion tests.
    if config.test_type == "proportion":
        ctrl_s = data.control_success if isinstance(data.control_success, int) else 0
        trt_s = data.treatment_success if isinstance(data.treatment_success, int) else 0
        if ctrl_s < _LOW_EVENTS_THRESHOLD or trt_s < _LOW_EVENTS_THRESHOLD:
            add(
                f"Low event counts: control={ctrl_s}, treatment={trt_s}. "
                "Normal approximation may not hold; consider exact tests."
            )

    # Underpowered: current n below required.
    current_total = data.control_n + data.treatment_n
    if current_total < required_sample_size.total_sample_size:
        pct = current_total / required_sample_size.total_sample_size * 100.0
        add(
            f"Underpowered: current n={current_total:,} is "
            f"{pct:.0f}% of required {required_sample_size.total_sample_size:,}."
        )

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_experiment(
    config: ExperimentConfig,
    data: ExperimentData,
    current_look: int | None = None,
) -> ExperimentAnalysis:
    """Run the full stats pipeline for a single experiment metric.

    Executes six stages in order, with graceful fallbacks at each optional step.

    Args:
        config: Experiment-level settings — alpha, power, test type, etc.
        data: Observed data for this analysis run.
        current_look: Which sequential look we are at (1-indexed).  Used to
                      extrapolate the planned final n for sequential boundaries.
                      If None, defaults to using the power-analysis required n.

    Returns:
        ExperimentAnalysis containing all stage results, an overall
        recommendation, a plain-English summary, and any warnings.

    Raises:
        ValueError: If config/data are inconsistent (wrong success type for
                    test_type, invalid CUPED covariate length, etc.).
    """
    logger.info(
        "analyze_experiment start: test_type=%s control_n=%d treatment_n=%d "
        "sequential_looks=%d n_metrics=%d has_cuped=%s",
        config.test_type,
        data.control_n,
        data.treatment_n,
        config.sequential_looks,
        config.n_metrics,
        config.has_cuped_data,
    )

    # ── Stage 1: Power analysis ──────────────────────────────────────────────
    logger.info("Stage 1: power analysis")
    if config.test_type == "proportion":
        if not isinstance(data.control_success, int):
            raise ValueError(
                "control_success must be int for test_type='proportion', "
                f"got {type(data.control_success).__name__}"
            )
        if not isinstance(data.treatment_success, int):
            raise ValueError(
                "treatment_success must be int for test_type='proportion', "
                f"got {type(data.treatment_success).__name__}"
            )
        required_sample_size = _power_analysis_proportion(
            data.control_success,
            data.control_n,
            data.treatment_success,
            data.treatment_n,
            config.alpha,
            config.power,
        )
    else:
        if not isinstance(data.control_success, list):
            raise ValueError(
                "control_success must be list[float] for test_type='mean'/'ratio', "
                f"got {type(data.control_success).__name__}"
            )
        if not isinstance(data.treatment_success, list):
            raise ValueError(
                "treatment_success must be list[float] for test_type='mean'/'ratio', "
                f"got {type(data.treatment_success).__name__}"
            )
        required_sample_size = _power_analysis_means(
            np.asarray(data.control_success, dtype=float),
            np.asarray(data.treatment_success, dtype=float),
            config.alpha,
            config.power,
        )

    # ── Stage 2: Hypothesis test ─────────────────────────────────────────────
    logger.info("Stage 2: hypothesis test (%s)", config.test_type)
    primary_result = _run_hypothesis_test(config, data)

    # ── Stage 3: Sequential analysis ─────────────────────────────────────────
    logger.info("Stage 3: sequential (looks=%d)", config.sequential_looks)
    sequential_status = _run_sequential(
        config, data, primary_result, required_sample_size, current_look
    )

    # ── Stage 4: CUPED ───────────────────────────────────────────────────────
    logger.info("Stage 4: CUPED (has_cuped_data=%s)", config.has_cuped_data)
    cuped_result = _run_cuped(config, data)

    # ── Stage 5: Multiple comparison correction ───────────────────────────────
    logger.info("Stage 5: corrections (n_metrics=%d)", config.n_metrics)
    corrected_results = _run_corrections(config, primary_result, cuped_result)

    # ── Stage 6: Recommendation ──────────────────────────────────────────────
    logger.info("Stage 6: recommendation")
    overall_recommendation, plain_english = _build_recommendation(
        config,
        data,
        primary_result,
        sequential_status,
        corrected_results,
        required_sample_size,
    )

    analysis_warnings = _collect_warnings(
        config, data, primary_result, required_sample_size
    )

    logger.info(
        "analyze_experiment complete: recommendation=%s significant=%s warnings=%d",
        overall_recommendation,
        primary_result.is_significant,
        len(analysis_warnings),
    )

    return ExperimentAnalysis(
        required_sample_size=required_sample_size,
        sequential_status=sequential_status,
        primary_result=primary_result,
        cuped_result=cuped_result,
        corrected_results=corrected_results,
        overall_recommendation=overall_recommendation,
        plain_english=plain_english,
        warnings=analysis_warnings,
    )

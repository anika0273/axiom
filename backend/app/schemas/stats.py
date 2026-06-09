"""Pydantic v2 request/response schemas for the stats API.

All request schemas validate inputs before they reach the service layer.
All response schemas define the public API contract independently of the
internal stats module data models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ── Request schemas ────────────────────────────────────────────────────────────


class SampleSizeRequest(BaseModel):
    """Inputs for POST /power/sample-size."""

    baseline_rate: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Current conversion rate (0 < baseline_rate < 1)",
    )
    mde: float = Field(
        ...,
        description="Minimum detectable effect — absolute change in rate (non-zero)",
    )
    alpha: float = Field(0.05, gt=0, lt=1, description="Type I error rate")
    power: float = Field(0.80, gt=0, lt=1, description="Target statistical power")

    @field_validator("mde")
    @classmethod
    def _mde_nonzero(cls, v: float) -> float:
        if v == 0.0:
            raise ValueError(
                "mde must be non-zero; a zero effect requires infinite samples"
            )
        return v


class RuntimeRequest(BaseModel):
    """Inputs for POST /power/runtime."""

    required_sample_size: int = Field(
        ..., gt=0, description="Total subjects needed across both groups"
    )
    daily_traffic: int = Field(
        ..., gt=0, description="Average number of eligible subjects per day"
    )


class AnalyzeConfigSchema(BaseModel):
    """Experiment-level configuration for a full-pipeline analysis."""

    alpha: float = Field(0.05, gt=0, lt=1, description="Two-tailed significance level")
    power: float = Field(
        0.80, gt=0, lt=1, description="Target power for sample-size stage"
    )
    test_type: Literal["proportion", "mean", "ratio"] = Field(
        "proportion", description="Which hypothesis test to run"
    )
    sequential_looks: int = Field(
        1, ge=1, description="Total planned looks; 1 = fixed-horizon"
    )
    n_metrics: int = Field(
        1, ge=1, description="Number of simultaneous metrics; >1 enables BH correction"
    )
    has_cuped_data: bool = Field(
        False, description="Whether cuped_covariates will be provided in data"
    )
    planned_n_per_group: int | None = Field(
        None, gt=0, description="Pre-specified per-group n (optional)"
    )


class AnalyzeDataSchema(BaseModel):
    """Observed experiment data for a single analysis run."""

    control_n: int = Field(..., gt=0, description="Subjects in the control group")
    treatment_n: int = Field(..., gt=0, description="Subjects in the treatment group")
    control_success: int | list[float] = Field(
        ...,
        description=(
            "Successes in control — int for proportion tests, "
            "list[float] of per-user values for mean/ratio tests"
        ),
    )
    treatment_success: int | list[float] = Field(
        ...,
        description="Successes in treatment — same type convention as control_success",
    )
    cuped_covariates: list[float] | None = Field(
        None,
        description=(
            "Pre-experiment covariate for all subjects (control first, then treatment). "
            "Required only when config.has_cuped_data is true."
        ),
    )


class AnalyzeRequest(BaseModel):
    """Full request body for POST /analyze."""

    config: AnalyzeConfigSchema = Field(default_factory=AnalyzeConfigSchema)
    data: AnalyzeDataSchema
    current_look: int | None = Field(
        None, ge=1, description="Current sequential look index (1-indexed)"
    )


# ── Response data shapes ───────────────────────────────────────────────────────


class PowerCurvePoint(BaseModel):
    n: float
    power: float


class SampleSizeData(BaseModel):
    control_size: int
    treatment_size: int
    total_sample_size: int
    cohens_d: float
    method_used: str
    power_curve: list[PowerCurvePoint]


class RuntimeData(BaseModel):
    days_expected: float
    days_lower_95: float
    days_upper_95: float
    weeks_expected: float


class HealthData(BaseModel):
    status: str
    version: str
    uptime: float


class TestResultData(BaseModel):
    is_significant: bool
    p_value: float
    confidence_interval: list[float]
    lift_pct: float
    lift_abs: float
    test_statistic: float
    test_type: str
    sample_warnings: list[str]
    interpretation: str


class SequentialDecisionData(BaseModel):
    decision: str
    required_z: float
    current_z: float
    info_fraction_complete: float
    interpretation: str


class CUPEDGroupData(BaseModel):
    group_name: str
    n_users: int
    pre_mean: float
    post_mean: float
    adjusted_mean: float


class CUPEDResultData(BaseModel):
    adjusted_test_result: TestResultData
    unadjusted_test_result: TestResultData
    theta: float
    variance_reduction_pct: float
    correlation_pre_post: float
    recommendation: str
    control_summary: CUPEDGroupData
    treatment_summary: CUPEDGroupData


class CorrectionResultData(BaseModel):
    method: str
    original_p: list[float]
    corrected_p: list[float]
    reject_mask: list[bool]
    n_rejected: int
    fwer_upper_bound: float
    fdr_upper_bound: float
    interpretation: str


class AnalysisData(BaseModel):
    required_sample_size: SampleSizeData
    sequential_status: SequentialDecisionData | None
    primary_result: TestResultData
    cuped_result: CUPEDResultData | None
    corrected_results: CorrectionResultData | None
    overall_recommendation: str
    plain_english: str
    warnings: list[str]


# ── Response envelopes ─────────────────────────────────────────────────────────


class SampleSizeResponse(BaseModel):
    data: SampleSizeData
    meta: dict = {}


class RuntimeResponse(BaseModel):
    data: RuntimeData
    meta: dict = {}


class HealthResponse(BaseModel):
    data: HealthData
    meta: dict = {}


class AnalyzeResponse(BaseModel):
    data: AnalysisData
    meta: dict = {}


# ── Serialization helper ───────────────────────────────────────────────────────


def _test_result_to_data(result: object) -> TestResultData:  # type: ignore[type-arg]
    return TestResultData(
        is_significant=result.is_significant,  # type: ignore[attr-defined]
        p_value=result.p_value,  # type: ignore[attr-defined]
        confidence_interval=list(result.confidence_interval),  # type: ignore[attr-defined]
        lift_pct=result.lift_pct,  # type: ignore[attr-defined]
        lift_abs=result.lift_abs,  # type: ignore[attr-defined]
        test_statistic=result.test_statistic,  # type: ignore[attr-defined]
        test_type=result.test_type,  # type: ignore[attr-defined]
        sample_warnings=result.sample_warnings,  # type: ignore[attr-defined]
        interpretation=result.interpretation,  # type: ignore[attr-defined]
    )


class SkippedTechnique(BaseModel):
    """Describes a statistical technique that was not run and why."""

    name: str
    reason: str
    what_it_would_show: str
    how_to_enable: str


class TechniquesReport(BaseModel):
    """Summary of which statistical / ML techniques ran vs were skipped."""

    ran: list[str]
    skipped: list[SkippedTechnique]


def analysis_to_response(analysis: object) -> AnalyzeResponse:  # type: ignore[type-arg]
    """Convert ExperimentAnalysis (with numpy arrays) to a JSON-safe AnalyzeResponse."""
    ss = analysis.required_sample_size  # type: ignore[attr-defined]
    sample_size = SampleSizeData(
        control_size=ss.control_size,
        treatment_size=ss.treatment_size,
        total_sample_size=ss.total_sample_size,
        cohens_d=ss.cohens_d,
        method_used=ss.method_used,
        power_curve=[
            PowerCurvePoint(n=p["n"], power=p["power"]) for p in ss.power_curve
        ],
    )

    sequential = None
    if analysis.sequential_status is not None:  # type: ignore[attr-defined]
        s = analysis.sequential_status  # type: ignore[attr-defined]
        sequential = SequentialDecisionData(
            decision=s.decision,
            required_z=s.required_z,
            current_z=s.current_z,
            info_fraction_complete=s.info_fraction_complete,
            interpretation=s.interpretation,
        )

    cuped = None
    if analysis.cuped_result is not None:  # type: ignore[attr-defined]
        c = analysis.cuped_result  # type: ignore[attr-defined]
        cuped = CUPEDResultData(
            adjusted_test_result=_test_result_to_data(c.adjusted_test_result),
            unadjusted_test_result=_test_result_to_data(c.unadjusted_test_result),
            theta=c.theta,
            variance_reduction_pct=c.variance_reduction_pct,
            correlation_pre_post=c.correlation_pre_post,
            recommendation=c.recommendation,
            control_summary=CUPEDGroupData(**c.control_summary.model_dump()),
            treatment_summary=CUPEDGroupData(**c.treatment_summary.model_dump()),
        )

    corrected = None
    if analysis.corrected_results is not None:  # type: ignore[attr-defined]
        cr = analysis.corrected_results  # type: ignore[attr-defined]
        corrected = CorrectionResultData(
            method=cr.method,
            original_p=list(cr.original_p),
            corrected_p=list(cr.corrected_p),
            reject_mask=[bool(x) for x in cr.reject_mask],
            n_rejected=cr.n_rejected,
            fwer_upper_bound=cr.fwer_upper_bound,
            fdr_upper_bound=cr.fdr_upper_bound,
            interpretation=cr.interpretation,
        )

    return AnalyzeResponse(
        data=AnalysisData(
            required_sample_size=sample_size,
            sequential_status=sequential,
            primary_result=_test_result_to_data(analysis.primary_result),  # type: ignore[attr-defined]
            cuped_result=cuped,
            corrected_results=corrected,
            overall_recommendation=analysis.overall_recommendation,  # type: ignore[attr-defined]
            plain_english=analysis.plain_english,  # type: ignore[attr-defined]
            warnings=analysis.warnings,  # type: ignore[attr-defined]
        )
    )

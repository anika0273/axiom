"""Pydantic v2 request/response schemas for the ML API.

All request schemas validate and coerce raw JSON into the typed structures
that the ML modules (hte, segments, anomaly) expect.  Response schemas define
the public API contract independently of internal dataclasses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Shared envelope ────────────────────────────────────────────────────────────


class MetaEmpty(BaseModel):
    """Empty meta block present on every response."""


# ── HTE schemas ────────────────────────────────────────────────────────────────


class HTERequest(BaseModel):
    """Inputs for POST /api/v1/ml/hte."""

    features: list[dict[str, float]] = Field(
        ...,
        description=(
            "User feature matrix as a list of records.  Each record is one "
            "subject; keys are feature names, values are numeric.  All records "
            "must share the same keys.  Caller must pre-encode categoricals."
        ),
        min_length=1,
    )
    treatment: list[float] = Field(
        ...,
        description="Binary treatment indicator per subject (0 = control, 1 = treatment).",
        min_length=1,
    )
    outcome: list[float] = Field(
        ...,
        description="Continuous outcome per subject (e.g. revenue, conversion indicator).",
        min_length=1,
    )
    random_state: int = Field(42, description="Seed for reproducibility.")
    bootstrap: bool = Field(
        False,
        description=(
            "Run bootstrap uncertainty estimation.  Off by default — too slow "
            "for real-time API use.  Enable for offline analysis."
        ),
    )
    n_bootstrap: int = Field(100, ge=10, le=500, description="Bootstrap resamples when bootstrap=True.")

    @model_validator(mode="after")
    def _lengths_match(self) -> "HTERequest":
        n = len(self.features)
        if len(self.treatment) != n or len(self.outcome) != n:
            raise ValueError(
                f"features ({n}), treatment ({len(self.treatment)}), and "
                f"outcome ({len(self.outcome)}) must all have the same length."
            )
        return self

    @field_validator("treatment")
    @classmethod
    def _treatment_is_binary(cls, v: list[float]) -> list[float]:
        for val in v:
            if val not in (0.0, 1.0):
                raise ValueError(f"treatment values must be 0 or 1, got {val}")
        return v


class HTEData(BaseModel):
    """Payload inside a successful HTE response."""

    ate: float = Field(..., description="Average treatment effect (lift_abs from the stats engine).")
    stability_score: float = Field(..., description="Mean pairwise ITE correlation across three refits (0–1).")
    top_interactions: list[str] = Field(..., description="Interaction features ranked by mean |SHAP|.")
    business_recommendation: str = Field(..., description="Plain-language targeting recommendation.")
    ite_point: list[float] = Field(..., description="Per-subject ITE point estimates.")
    ite_uncertainty: list[float] = Field(
        ...,
        description="Per-subject ITE half-width of 90% bootstrap PI (zeros when bootstrap=False).",
    )


class HTEResponse(BaseModel):
    """Response envelope for POST /api/v1/ml/hte."""

    data: HTEData
    meta: MetaEmpty = Field(default_factory=MetaEmpty)


# ── Segments schemas ───────────────────────────────────────────────────────────


class SegmentsRequest(BaseModel):
    """Inputs for POST /api/v1/ml/segments."""

    features: list[dict[str, float]] = Field(
        ...,
        description="User feature matrix — same format as HTERequest.features.",
        min_length=1,
    )
    treatment: list[float] = Field(..., min_length=1)
    outcome: list[float] = Field(..., min_length=1)
    max_k: int = Field(8, ge=2, le=20, description="Maximum number of clusters to evaluate.")
    random_state: int = Field(42)

    @model_validator(mode="after")
    def _lengths_match(self) -> "SegmentsRequest":
        n = len(self.features)
        if len(self.treatment) != n or len(self.outcome) != n:
            raise ValueError(
                f"features ({n}), treatment ({len(self.treatment)}), and "
                f"outcome ({len(self.outcome)}) must all have the same length."
            )
        return self

    @field_validator("treatment")
    @classmethod
    def _treatment_is_binary(cls, v: list[float]) -> list[float]:
        for val in v:
            if val not in (0.0, 1.0):
                raise ValueError(f"treatment values must be 0 or 1, got {val}")
        return v


class SegmentProfileOut(BaseModel):
    """One segment's profile."""

    id: int
    size_pct: float
    lift: float
    lift_uncertainty: float
    description: str
    top_features: dict[str, list[float]] = Field(
        ...,
        description="Feature name → [segment_mean, global_mean].  JSON keys must be strings.",
    )
    significant: bool
    low_confidence: bool


class SegmentsData(BaseModel):
    """Payload inside a successful segments response."""

    optimal_k: int
    silhouette_score: float
    segments: list[SegmentProfileOut]
    responsive_segments: list[int]
    stability_scores: dict[str, float] = Field(
        ..., description="Segment id (string) → Jaccard stability score."
    )
    overall_recommendation: str
    low_confidence: bool


class SegmentsResponse(BaseModel):
    """Response envelope for POST /api/v1/ml/segments."""

    data: SegmentsData
    meta: MetaEmpty = Field(default_factory=MetaEmpty)


# ── Validate schemas ───────────────────────────────────────────────────────────


class DailyMetricRecord(BaseModel):
    """One day of experiment data."""

    date: str = Field(..., description="ISO-8601 date string, e.g. '2024-01-15'.")
    control_metric: float
    treatment_metric: float
    n_control: float = Field(..., gt=0)
    n_treatment: float = Field(..., gt=0)


class ValidateRequest(BaseModel):
    """Inputs for POST /api/v1/ml/validate."""

    daily_metrics: list[DailyMetricRecord] = Field(
        ...,
        min_length=7,
        description="Daily experiment data.  Must contain at least 7 days.",
    )
    expected_ratio: float = Field(
        0.5,
        gt=0,
        lt=1,
        description="Expected fraction of subjects in the treatment group.",
    )


class ValidationCheckOut(BaseModel):
    """Result of one validity check."""

    name: str
    passed: bool
    score: float
    severity: Literal["info", "warning", "critical"]
    description: str
    action: str


class ValidateData(BaseModel):
    """Payload inside a successful validate response."""

    overall_validity: Literal["VALID", "WARNING", "INVALID"]
    checks: list[ValidationCheckOut]
    recommendation: str
    can_trust_results: bool


class ValidateResponse(BaseModel):
    """Response envelope for POST /api/v1/ml/validate."""

    data: ValidateData
    meta: MetaEmpty = Field(default_factory=MetaEmpty)


# ── Unified ML analysis schemas ────────────────────────────────────────────────


class MLAnalysisRequest(BaseModel):
    """Inputs for POST /api/v1/ml/analyze."""

    control_values: list[float] = Field(
        ...,
        min_length=10,
        description="Outcome per subject in the control group (min 10).",
    )
    treatment_values: list[float] = Field(
        ...,
        min_length=10,
        description="Outcome per subject in the treatment group (min 10).",
    )
    user_features: list[dict[str, float]] | None = Field(
        None,
        description="Per-subject feature matrix.  Enables HTE and segment modules.",
    )
    daily_metrics: list[DailyMetricRecord] | None = Field(
        None,
        description="Daily time-series data.  Enables anomaly and novelty modules.",
    )
    experiment_id: UUID | None = Field(
        None,
        description="If provided, the result is stored in experiment_results.",
    )


class ModuleStatusOut(BaseModel):
    """Execution record for one ML module."""

    module: str
    status: Literal["completed", "skipped", "failed"]
    skip_reason: str | None = None
    duration_seconds: float


class MLAnalysisResultData(BaseModel):
    """Payload inside a successful ML analysis response."""

    overall_verdict: Literal["CLEAN", "NEEDS_REVIEW", "INVALID"]
    key_insights: list[str]
    capability_report: list[ModuleStatusOut]
    can_trust_results: bool
    recommendation: str
    experiment_id: UUID | None = None
    result_id: UUID | None = None


class MLAnalysisResponse(BaseModel):
    """Response envelope for POST /api/v1/ml/analyze."""

    data: MLAnalysisResultData
    meta: MetaEmpty = Field(default_factory=MetaEmpty)


# ── Experiment CRUD schemas ────────────────────────────────────────────────────


class ExperimentCreate(BaseModel):
    """Request body for POST /api/v1/experiments."""

    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    hypothesis: str | None = None
    experiment_type: Literal["proportion", "mean", "ratio"]
    baseline_metric: float = Field(..., gt=0)
    mde: float = Field(..., gt=0, lt=1, description="Minimum detectable effect (0–1).")
    alpha: float = Field(0.05, gt=0, lt=1)
    power: float = Field(0.80, gt=0, lt=1)
    daily_traffic_estimate: int | None = Field(None, gt=0)


class ExperimentStatusUpdate(BaseModel):
    """Request body for PATCH /api/v1/experiments/{id}/status."""

    status: Literal["running", "completed", "stopped_early"]


class StoredResultSummary(BaseModel):
    """Compact summary of a stored ExperimentResult row."""

    id: UUID
    overall_verdict: str | None = None
    can_trust_results: bool | None = None
    recommendation: str | None = None
    key_insights: list[str] = Field(default_factory=list)
    analyzed_at: datetime
    report_markdown: str | None = None


class ExperimentResponse(BaseModel):
    """Response body for experiment CRUD endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    status: str
    experiment_type: str
    hypothesis: str | None = None
    baseline_metric: float
    mde: float
    alpha: float
    power: float
    daily_traffic_estimate: int | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latest_result: StoredResultSummary | None = None


class ExperimentEnvelope(BaseModel):
    """Single-experiment response envelope."""

    data: ExperimentResponse
    meta: MetaEmpty = Field(default_factory=MetaEmpty)


class ExperimentListMeta(BaseModel):
    """Pagination metadata for experiment list responses."""

    total: int
    page: int
    page_size: int


class ExperimentListEnvelope(BaseModel):
    """Paginated list response envelope."""

    data: list[ExperimentResponse]
    meta: ExperimentListMeta

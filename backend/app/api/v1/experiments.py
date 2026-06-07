"""Experiment CRUD router — /api/v1/experiments/*.

Provides create, list, get, and status-update operations.  All DB access goes
through the repository layer; no SQLAlchemy code lives here.

Rate limits: 60 req/min per IP for reads; 30 req/min for writes.

Note: this file intentionally omits 'from __future__ import annotations'.
With that import active, slowapi's @limiter.limit wrapper copies annotations
as strings but has different __globals__, preventing FastAPI from resolving
Pydantic model types and causing body params to be treated as query params.
"""

import io
import logging
from uuid import UUID

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_request_id, limiter
from app.models.experiment import ExperimentResult
from app.repositories import experiment_repo, result_repo, subject_repo
from app.schemas.ml import (
    ExperimentCreate,
    ExperimentEnvelope,
    ExperimentListEnvelope,
    ExperimentListMeta,
    ExperimentResponse,
    ExperimentStatusUpdate,
    MLAnalysisRequest,
    MLAnalysisResultData,
    StoredResultSummary,
    SubjectUploadEnvelope,
    SubjectUploadResponse,
)
from app.schemas.stats import AnalysisData, analysis_to_response
from app.services import analysis_service
from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


# ---------------------------------------------------------------------------
# Response schemas for the /analyze endpoint
# ---------------------------------------------------------------------------


class ExperimentAnalyzeData(BaseModel):
    """Combined stats + ML result returned by POST /{id}/analyze."""

    experiment_id: UUID
    result_id: UUID | None = None
    stats: AnalysisData
    ml: MLAnalysisResultData
    data_source: str = "synthetic"  # "real" | "synthetic"


class ExperimentAnalyzeResponse(BaseModel):
    """Envelope wrapping ExperimentAnalyzeData."""

    data: ExperimentAnalyzeData
    meta: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result_to_summary(record: ExperimentResult) -> StoredResultSummary:
    """Extract the summary fields from a stored ExperimentResult row."""
    payload = record.full_analysis_json or {}
    return StoredResultSummary(
        id=record.id,
        overall_verdict=payload.get("overall_verdict"),
        can_trust_results=payload.get("can_trust_results"),
        recommendation=payload.get("recommendation"),
        key_insights=payload.get("key_insights", []),
        analyzed_at=record.analyzed_at,
        report_markdown=record.report_markdown,
    )


async def _experiment_response(
    exp,
    db: AsyncSession,
) -> ExperimentResponse:
    """Build an ExperimentResponse, attaching the latest result if present."""
    latest = await result_repo.get_latest_result(db, exp.id)
    return ExperimentResponse(
        id=exp.id,
        name=exp.name,
        description=exp.description,
        status=exp.status.value if hasattr(exp.status, "value") else exp.status,
        experiment_type=(
            exp.experiment_type.value
            if hasattr(exp.experiment_type, "value")
            else exp.experiment_type
        ),
        hypothesis=exp.hypothesis,
        baseline_metric=exp.baseline_metric,
        mde=exp.mde,
        alpha=exp.alpha,
        power=exp.power,
        daily_traffic_estimate=exp.daily_traffic_estimate,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
        started_at=exp.started_at,
        completed_at=exp.completed_at,
        latest_result=_result_to_summary(latest) if latest else None,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/experiments — create
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ExperimentEnvelope,
    status_code=201,
    summary="Create a new experiment",
)
@limiter.limit("30/minute")
async def create_experiment(
    request: Request,
    response: Response,
    body: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
) -> ExperimentEnvelope:
    """Create an experiment in draft status and return its full representation."""
    req_id = get_request_id(request)
    logger.info("create_experiment req=%s name=%r", req_id, body.name)
    exp = await experiment_repo.create_experiment(db, body)
    return ExperimentEnvelope(data=await _experiment_response(exp, db))


# ---------------------------------------------------------------------------
# GET /api/v1/experiments — list
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ExperimentListEnvelope,
    summary="List experiments (newest first)",
)
@limiter.limit("60/minute")
async def list_experiments(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ExperimentListEnvelope:
    """Return a paginated list of experiments ordered by creation time."""
    req_id = get_request_id(request)
    logger.info("list_experiments req=%s page=%d page_size=%d", req_id, page, page_size)
    experiments, total = await experiment_repo.list_experiments(db, page, page_size)
    items = [await _experiment_response(exp, db) for exp in experiments]
    return ExperimentListEnvelope(
        data=items,
        meta=ExperimentListMeta(total=total, page=page, page_size=page_size),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/experiments/{id} — retrieve one
# ---------------------------------------------------------------------------


@router.get(
    "/{experiment_id}",
    response_model=ExperimentEnvelope,
    summary="Get one experiment",
)
@limiter.limit("60/minute")
async def get_experiment(
    request: Request,
    response: Response,
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ExperimentEnvelope:
    """Return a single experiment with its latest analysis result if available."""
    req_id = get_request_id(request)
    logger.info("get_experiment req=%s id=%s", req_id, experiment_id)
    exp = await experiment_repo.get_experiment(db, experiment_id)
    if exp is None:
        raise HTTPException(
            status_code=404, detail=f"Experiment {experiment_id} not found."
        )
    return ExperimentEnvelope(data=await _experiment_response(exp, db))


# ---------------------------------------------------------------------------
# PATCH /api/v1/experiments/{id}/status — update status
# ---------------------------------------------------------------------------


@router.patch(
    "/{experiment_id}/status",
    response_model=ExperimentEnvelope,
    summary="Update experiment status",
)
@limiter.limit("30/minute")
async def update_experiment_status(
    request: Request,
    response: Response,
    experiment_id: UUID,
    body: ExperimentStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> ExperimentEnvelope:
    """Transition an experiment to a new status."""
    req_id = get_request_id(request)
    logger.info(
        "update_status req=%s id=%s status=%s", req_id, experiment_id, body.status
    )
    exp = await experiment_repo.update_status(db, experiment_id, body.status)
    if exp is None:
        raise HTTPException(
            status_code=404, detail=f"Experiment {experiment_id} not found."
        )
    return ExperimentEnvelope(data=await _experiment_response(exp, db))


# ---------------------------------------------------------------------------
# POST /api/v1/experiments/{id}/analyze — run full analysis pipeline
# ---------------------------------------------------------------------------


@router.post(
    "/{experiment_id}/analyze",
    response_model=ExperimentAnalyzeResponse,
    status_code=200,
    summary="Run full stats + ML analysis for an experiment",
    description=(
        "Builds representative outcome data from the experiment's stored "
        "configuration (baseline_metric, mde, experiment_type), runs the stats "
        "pipeline (z-test / t-test, sequential, CUPED) and the ML pipeline "
        "(anomaly, novelty, HTE, segments), persists the result, and returns a "
        "combined analysis payload. Returns 404 if the experiment is not found; "
        "422 if no metrics have been configured for it."
    ),
)
@limiter.limit("10/minute")
async def analyze_experiment_route(
    request: Request,
    response: Response,
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ExperimentAnalyzeResponse:
    """Run stats + ML pipeline for an experiment using its stored configuration."""
    req_id = get_request_id(request)
    logger.info("analyze_experiment req=%s id=%s", req_id, experiment_id)

    # ── 1. Fetch experiment ──────────────────────────────────────────────────
    exp = await experiment_repo.get_experiment(db, experiment_id)
    if exp is None:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {experiment_id} not found.",
        )

    # ── 2. Check for configured metrics ─────────────────────────────────────
    metrics = await experiment_repo.get_metrics(db, experiment_id)
    if not metrics:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Experiment {experiment_id} has no metrics configured. "
                "Add at least one metric before running analysis."
            ),
        )

    # ── 3. Build data: real subjects if uploaded, else synthetic ─────────────
    exp_type = (
        exp.experiment_type.value
        if hasattr(exp.experiment_type, "value")
        else str(exp.experiment_type)
    )

    if await subject_repo.has_subject_data(db, experiment_id):
        data_source = "real"
        subjects = await subject_repo.get_subjects_for_experiment(db, experiment_id)
        ctrl_rows = [s for s in subjects if s.variant == 0]
        trt_rows = [s for s in subjects if s.variant == 1]
        ctrl_outcomes = [s.outcome for s in ctrl_rows]
        trt_outcomes = [s.outcome for s in trt_rows]

        if exp_type == "proportion":
            stats_data = ExperimentData(
                control_n=len(ctrl_outcomes),
                treatment_n=len(trt_outcomes),
                control_success=int(sum(ctrl_outcomes)),
                treatment_success=int(sum(trt_outcomes)),
            )
        else:
            stats_data = ExperimentData(
                control_n=len(ctrl_outcomes),
                treatment_n=len(trt_outcomes),
                control_success=ctrl_outcomes,
                treatment_success=trt_outcomes,
            )

        # Subsample symmetrically so ML modules see both groups
        n_half = min(len(ctrl_rows), len(trt_rows), 500)
        sample_ctrl = ctrl_rows[:n_half]
        sample_trt = trt_rows[:n_half]
        ml_ctrl = [s.outcome for s in sample_ctrl]
        ml_trt = [s.outcome for s in sample_trt]
        sample = sample_ctrl + sample_trt

        # Use uploaded covariates when available; synthesise otherwise
        has_covariates = any(s.covariates for s in sample)
        if has_covariates:
            cov_keys = sorted({k for s in sample if s.covariates for k in s.covariates})
            user_features: list[dict[str, float]] = []
            for s in sample:
                row: dict[str, float] = {}
                for k in cov_keys:
                    try:
                        row[k] = float((s.covariates or {}).get(k, 0.0))
                    except (TypeError, ValueError):
                        row[k] = 0.0
                user_features.append(row)
        else:
            rng = np.random.default_rng(int(experiment_id) % 2**32)
            n_feat = len(sample)
            feat_device = rng.integers(0, 3, size=n_feat).astype(float)
            feat_tenure = rng.exponential(90.0, size=n_feat)
            feat_company = rng.gamma(2.0, 2.0, size=n_feat)
            user_features = [
                {
                    "device_type": float(feat_device[i]),
                    "user_tenure_days": float(feat_tenure[i]),
                    "company_size_log": float(feat_company[i]),
                }
                for i in range(n_feat)
            ]
    else:
        data_source = "synthetic"
        # 5 000+ subjects per group so integer-rounding can't flatten a real effect
        n = max(exp.daily_traffic_estimate or 5000, 5000)
        rng = np.random.default_rng(int(experiment_id) % 2**32)

        if exp_type == "proportion":
            ctrl_p = float(np.clip(exp.baseline_metric, 0.001, 0.999))
            # Absolute-lift interpretation: treatment_rate = baseline + mde
            trt_p = float(np.clip(ctrl_p + float(exp.mde), ctrl_p + 1e-6, 0.999))
            ctrl_arr = rng.binomial(1, ctrl_p, size=n).astype(float)
            trt_arr = rng.binomial(1, trt_p, size=n).astype(float)
            stats_data = ExperimentData(
                control_n=n,
                treatment_n=n,
                control_success=int(ctrl_arr.sum()),
                treatment_success=int(trt_arr.sum()),
            )
        else:
            mu = float(exp.baseline_metric)
            sigma = max(abs(mu) * 0.3, 0.01)
            # Absolute-lift interpretation: treatment_mean = baseline + mde
            ctrl_arr = rng.normal(mu, sigma, size=n)
            trt_arr = rng.normal(mu + float(exp.mde), sigma, size=n)
            stats_data = ExperimentData(
                control_n=n,
                treatment_n=n,
                control_success=ctrl_arr.tolist(),
                treatment_success=trt_arr.tolist(),
            )

        n_ml = min(n, 1000)
        ml_ctrl = ctrl_arr[:n_ml].tolist()
        ml_trt = trt_arr[:n_ml].tolist()
        n_feat = 2 * n_ml
        feat_device = rng.integers(0, 3, size=n_feat).astype(float)
        feat_tenure = rng.exponential(90.0, size=n_feat)
        feat_company = rng.gamma(2.0, 2.0, size=n_feat)
        user_features = [
            {
                "device_type": float(feat_device[i]),
                "user_tenure_days": float(feat_tenure[i]),
                "company_size_log": float(feat_company[i]),
            }
            for i in range(n_feat)
        ]

    # ── 4. Run stats pipeline ────────────────────────────────────────────────
    stats_config = ExperimentConfig(
        test_type=exp_type,
        alpha=float(exp.alpha),
        power=float(exp.power),
    )
    try:
        stats_analysis = analyze_experiment(stats_config, stats_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stats_envelope = analysis_to_response(stats_analysis)

    # ── 5. Run ML pipeline (stores result) ───────────────────────────────────
    ml_body = MLAnalysisRequest(
        control_values=ml_ctrl,
        treatment_values=ml_trt,
        user_features=user_features,
        experiment_id=experiment_id,
    )
    try:
        ml_result = await analysis_service.run_analysis(ml_body, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ── 6. Return combined response ──────────────────────────────────────────
    return ExperimentAnalyzeResponse(
        data=ExperimentAnalyzeData(
            experiment_id=experiment_id,
            result_id=ml_result.result_id,
            stats=stats_envelope.data,
            ml=ml_result,
            data_source=data_source,
        )
    )


# ---------------------------------------------------------------------------
# POST /api/v1/experiments/{id}/upload-data — upload subject-level CSV
# ---------------------------------------------------------------------------


@router.post(
    "/{experiment_id}/upload-data",
    response_model=SubjectUploadEnvelope,
    status_code=200,
    summary="Upload subject-level CSV data for an experiment",
)
@limiter.limit("10/minute")
async def upload_subject_data(
    request: Request,
    response: Response,
    experiment_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> SubjectUploadEnvelope:
    """Parse a CSV upload and persist one row per subject into experiment_subjects."""
    req_id = get_request_id(request)
    logger.info("upload_subject_data req=%s id=%s", req_id, experiment_id)

    # ── 1. Read bytes ────────────────────────────────────────────────────────
    content = await file.read()

    # ── 2. Parse CSV ─────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {exc}") from exc

    # ── 3. Validate required columns ─────────────────────────────────────────
    required = {"subject_id", "variant", "outcome"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required columns: {sorted(missing)}",
        )

    # ── 4. Validate not empty ────────────────────────────────────────────────
    if df.empty:
        raise HTTPException(status_code=422, detail="CSV contains no data rows.")

    # ── 5. Validate row limit ────────────────────────────────────────────────
    if len(df) > 2_000_000:
        raise HTTPException(status_code=422, detail="CSV exceeds 2,000,000 row limit.")

    # ── 6. Check experiment exists ───────────────────────────────────────────
    exp = await experiment_repo.get_experiment(db, experiment_id)
    if exp is None:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {experiment_id} not found.",
        )

    warnings: list[str] = []
    rows_rejected = 0

    # ── 7. Filter invalid variant rows ───────────────────────────────────────
    df["variant"] = pd.to_numeric(df["variant"], errors="coerce")
    bad_variant = df["variant"].isna() | ~df["variant"].isin([0, 1])
    n_bad_variant = int(bad_variant.sum())
    if n_bad_variant:
        warnings.append(f"{n_bad_variant} rows rejected: variant must be 0 or 1")
        rows_rejected += n_bad_variant
        df = df[~bad_variant]

    # ── 8. Coerce outcome to float ───────────────────────────────────────────
    df["outcome"] = pd.to_numeric(df["outcome"], errors="coerce")
    bad_outcome = df["outcome"].isna()
    n_bad_outcome = int(bad_outcome.sum())
    if n_bad_outcome:
        warnings.append(f"{n_bad_outcome} rows rejected: outcome could not be parsed as a number")
        rows_rejected += n_bad_outcome
        df = df[~bad_outcome]

    # ── 9. Build rows for bulk insert ────────────────────────────────────────
    extra_cols = [c for c in df.columns if c not in {"subject_id", "variant", "outcome"}]
    rows = []
    for record in df.to_dict(orient="records"):
        cov = {c: record[c] for c in extra_cols} if extra_cols else None
        rows.append({
            "subject_id": str(record["subject_id"]),
            "variant": int(record["variant"]),
            "outcome": float(record["outcome"]),
            "covariates": cov,
        })

    # ── 10. Bulk insert ──────────────────────────────────────────────────────
    inserted = await subject_repo.bulk_insert_subjects(db, experiment_id, rows)

    # ── 11. Return envelope ──────────────────────────────────────────────────
    return SubjectUploadEnvelope(
        data=SubjectUploadResponse(
            rows_accepted=inserted,
            rows_rejected=rows_rejected,
            experiment_id=experiment_id,
            warnings=warnings,
        )
    )

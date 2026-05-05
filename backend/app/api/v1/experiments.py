"""Experiment CRUD router — /api/v1/experiments/*.

Provides create, list, get, and status-update operations.  All DB access goes
through the repository layer; no SQLAlchemy code lives here.

Rate limits: 60 req/min per IP for reads; 30 req/min for writes.

Note: this file intentionally omits 'from __future__ import annotations'.
With that import active, slowapi's @limiter.limit wrapper copies annotations
as strings but has different __globals__, preventing FastAPI from resolving
Pydantic model types and causing body params to be treated as query params.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_request_id, limiter
from app.models.experiment import ExperimentResult
from app.repositories import experiment_repo, result_repo
from app.schemas.ml import (
    ExperimentCreate,
    ExperimentEnvelope,
    ExperimentListEnvelope,
    ExperimentListMeta,
    ExperimentResponse,
    ExperimentStatusUpdate,
    StoredResultSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


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
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found.")
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
    logger.info("update_status req=%s id=%s status=%s", req_id, experiment_id, body.status)
    exp = await experiment_repo.update_status(db, experiment_id, body.status)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found.")
    return ExperimentEnvelope(data=await _experiment_response(exp, db))

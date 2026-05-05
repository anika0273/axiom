"""ML API router — /api/v1/ml/*.

Exposes ML modules as REST endpoints:
  - Stateless: HTE, segments, validate (no DB)
  - DB-backed:  analyze (full pipeline + optional persistence), get analysis

Rate limits (via slowapi):
  - HTE + segments: 30 req/min per IP (expensive computation)
  - validate:       60 req/min per IP (cheaper; four lightweight checks)
  - analyze:        20 req/min per IP
  - get analysis:   60 req/min per IP
"""

import logging
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_request_id, limiter
from app.ml.anomaly import validate_experiment
from app.ml.hte import fit_hte_model
from app.ml.segments import discover_segments
from app.repositories import result_repo
from app.schemas.ml import (
    HTEData,
    HTERequest,
    HTEResponse,
    MLAnalysisRequest,
    MLAnalysisResponse,
    ModuleStatusOut,
    SegmentProfileOut,
    SegmentsData,
    SegmentsRequest,
    SegmentsResponse,
    StoredResultSummary,
    ValidateData,
    ValidateRequest,
    ValidateResponse,
    ValidationCheckOut,
)
from app.services import analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request_to_frames(
    features: list[dict[str, float]],
    treatment: list[float],
    outcome: list[float],
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Convert validated request lists into pandas structures.

    Args:
        features: List of per-subject feature dicts.
        treatment: List of 0/1 treatment indicators.
        outcome: List of per-subject outcome values.

    Returns:
        (X, treatment_series, outcome_series)
    """
    X = pd.DataFrame(features)
    t = pd.Series(treatment, dtype=float)
    y = pd.Series(outcome, dtype=float)
    return X, t, y


# ---------------------------------------------------------------------------
# HTE endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/hte",
    response_model=HTEResponse,
    summary="Heterogeneous Treatment Effect analysis",
    description=(
        "Fits an XGBoost model with treatment–feature interactions, ranks "
        "feature modifiers via SHAP, and returns per-subject ITE estimates "
        "with an optional bootstrap uncertainty band.  Requires randomised "
        "A/B data — causal interpretation requires randomisation."
    ),
)
@limiter.limit("30/minute")
async def run_hte(
    request: Request,
    response: Response,
    body: HTERequest,
) -> HTEResponse:
    """Run HTE analysis and return ATE, SHAP-ranked interactions, and ITEs."""
    req_id = get_request_id(request)
    n = len(body.features)
    logger.info("hte req=%s n=%d bootstrap=%s", req_id, n, body.bootstrap)

    X, t, y = _request_to_frames(body.features, body.treatment, body.outcome)

    try:
        model = fit_hte_model(
            X, t, y,
            random_state=body.random_state,
            bootstrap=body.bootstrap,
            n_bootstrap=body.n_bootstrap,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return HTEResponse(
        data=HTEData(
            ate=model.ate,
            stability_score=model.stability_score,
            top_interactions=model.top_interactions,
            business_recommendation=model.business_recommendation,
            ite_point=model.ite_point.tolist(),
            ite_uncertainty=model.ite_uncertainty.tolist(),
        ),
    )


# ---------------------------------------------------------------------------
# Segments endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/segments",
    response_model=SegmentsResponse,
    summary="Automatic treatment-responsive segment discovery",
    description=(
        "Scales features, selects the optimal cluster count via silhouette "
        "analysis, profiles each cluster with per-segment lift tests, and "
        "produces a plain-English rollout recommendation."
    ),
)
@limiter.limit("30/minute")
async def run_segments(
    request: Request,
    response: Response,
    body: SegmentsRequest,
) -> SegmentsResponse:
    """Discover user segments with heterogeneous treatment response."""
    req_id = get_request_id(request)
    n = len(body.features)
    logger.info("segments req=%s n=%d max_k=%d", req_id, n, body.max_k)

    X, t, y = _request_to_frames(body.features, body.treatment, body.outcome)

    try:
        analysis = discover_segments(
            X, t, y,
            max_k=body.max_k,
            random_state=body.random_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    segments_out = [
        SegmentProfileOut(
            id=seg.id,
            size_pct=seg.size_pct,
            lift=seg.lift,
            lift_uncertainty=seg.lift_uncertainty,
            description=seg.description,
            # top_features values are (float, float) tuples; JSON needs lists.
            top_features={k: list(v) for k, v in seg.top_features.items()},
            significant=seg.significant,
            low_confidence=seg.low_confidence,
        )
        for seg in analysis.segments
    ]

    return SegmentsResponse(
        data=SegmentsData(
            optimal_k=analysis.optimal_k,
            silhouette_score=analysis.silhouette_score,
            segments=segments_out,
            responsive_segments=analysis.responsive_segments,
            # JSON object keys must be strings.
            stability_scores={str(k): v for k, v in analysis.stability_scores.items()},
            overall_recommendation=analysis.overall_recommendation,
            low_confidence=analysis.low_confidence,
        ),
    )


# ---------------------------------------------------------------------------
# Validate endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/validate",
    response_model=ValidateResponse,
    summary="Experiment data validity guardrails",
    description=(
        "Runs four independent checks: SRM (chi-squared), outlier days "
        "(IsolationForest), metric drift (CUSUM), and volume spikes (3σ).  "
        "Returns an overall VALID / WARNING / INVALID verdict with per-check "
        "details and a plain-English recommendation."
    ),
)
@limiter.limit("60/minute")
async def run_validate(
    request: Request,
    response: Response,
    body: ValidateRequest,
) -> ValidateResponse:
    """Validate experiment data quality and return a trust verdict."""
    req_id = get_request_id(request)
    n_days = len(body.daily_metrics)
    logger.info("validate req=%s n_days=%d", req_id, n_days)

    daily_df = pd.DataFrame([r.model_dump() for r in body.daily_metrics])
    daily_df["date"] = pd.to_datetime(daily_df["date"])

    try:
        validation = validate_experiment(daily_df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    checks_out = [
        ValidationCheckOut(
            name=c.name,
            passed=bool(c.passed),
            score=c.score,
            severity=c.severity,
            description=c.description,
            action=c.action,
        )
        for c in validation.checks
    ]

    return ValidateResponse(
        data=ValidateData(
            overall_validity=validation.overall_validity,
            checks=checks_out,
            recommendation=validation.recommendation,
            can_trust_results=bool(validation.can_trust_results),
        ),
    )


# ---------------------------------------------------------------------------
# Full ML analysis (orchestrated)
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=MLAnalysisResponse,
    summary="Run full ML analysis pipeline",
    description=(
        "Orchestrates all four ML modules (anomaly, novelty, HTE, segments) "
        "from a single request.  Modules are skipped when their prerequisite "
        "data is absent.  If experiment_id is provided, the result is persisted "
        "in experiment_results.full_analysis_json."
    ),
)
@limiter.limit("20/minute")
async def run_analyze(
    request: Request,
    response: Response,
    body: MLAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> MLAnalysisResponse:
    """Execute the ML pipeline and return a unified verdict with key insights."""
    req_id = get_request_id(request)
    logger.info(
        "analyze req=%s n_ctrl=%d n_trt=%d exp_id=%s",
        req_id,
        len(body.control_values),
        len(body.treatment_values),
        body.experiment_id,
    )

    try:
        result_data = await analysis_service.run_analysis(body, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MLAnalysisResponse(data=result_data)


# ---------------------------------------------------------------------------
# Retrieve stored ML analysis for an experiment
# ---------------------------------------------------------------------------


@router.get(
    "/experiments/{experiment_id}/analysis",
    response_model=MLAnalysisResponse,
    summary="Retrieve stored ML analysis for an experiment",
    description=(
        "Returns the most recent ML analysis result persisted for the given "
        "experiment.  Returns 404 when no analysis has been run yet."
    ),
)
@limiter.limit("60/minute")
async def get_experiment_analysis(
    request: Request,
    response: Response,
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MLAnalysisResponse:
    """Fetch the latest stored ML result for experiment_id."""
    req_id = get_request_id(request)
    logger.info("get_analysis req=%s exp_id=%s", req_id, experiment_id)

    record = await result_repo.get_latest_result(db, experiment_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No ML analysis found for experiment {experiment_id}.",
        )

    payload = record.full_analysis_json or {}
    result_data = MLAnalysisResultData_from_json(payload, record, experiment_id)
    return MLAnalysisResponse(data=result_data)


def MLAnalysisResultData_from_json(
    payload: dict,
    record,
    experiment_id: UUID,
) -> "MLAnalysisResponse.model_fields['data'].annotation":  # type: ignore[return]
    """Reconstruct MLAnalysisResultData from a stored JSONB payload."""
    from app.schemas.ml import MLAnalysisResultData

    return MLAnalysisResultData(
        overall_verdict=payload.get("overall_verdict", "NEEDS_REVIEW"),
        key_insights=payload.get("key_insights", []),
        capability_report=[
            ModuleStatusOut(**s) for s in payload.get("capability_report", [])
        ],
        can_trust_results=payload.get("can_trust_results", False),
        recommendation=payload.get("recommendation", ""),
        experiment_id=experiment_id,
        result_id=record.id,
    )

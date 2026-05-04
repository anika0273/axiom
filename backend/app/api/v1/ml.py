"""ML API router — /api/v1/ml/*.

Exposes the three ML modules (HTE, segments, anomaly) as stateless REST
endpoints.  Each request deserialises JSON into pandas structures, calls the
relevant ML function, and serialises the result back to the response envelope.

Rate limits (via slowapi):
  - HTE + segments: 30 req/min per IP (expensive computation)
  - validate:       60 req/min per IP (cheaper; four lightweight checks)
"""

import logging
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.dependencies import get_request_id, limiter
from app.ml.anomaly import validate_experiment
from app.ml.hte import fit_hte_model
from app.ml.segments import discover_segments
from app.schemas.ml import (
    HTEData,
    HTERequest,
    HTEResponse,
    SegmentProfileOut,
    SegmentsData,
    SegmentsRequest,
    SegmentsResponse,
    ValidateData,
    ValidateRequest,
    ValidateResponse,
    ValidationCheckOut,
)

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

"""Stats API router — /api/v1/stats/*.

Endpoints are stateless: they accept raw inputs, run the stats pipeline,
and return results.  No database calls are made here.

Rate limits (via slowapi):
  - All endpoints: 60 req/min per IP

Note: slowapi with headers_enabled=True requires a `response: Response`
parameter so it can inject X-RateLimit-* headers.  Do NOT remove it.
"""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.dependencies import StatsEngine, get_request_id, get_stats_engine, limiter
from app.schemas.stats import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthData,
    HealthResponse,
    PowerCurvePoint,
    RuntimeData,
    RuntimeRequest,
    RuntimeResponse,
    SampleSizeData,
    SampleSizeRequest,
    SampleSizeResponse,
    analysis_to_response,
)
from app.stats.engine import ExperimentConfig, ExperimentData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Stats engine health check",
    description="Returns service status, application version, and uptime in seconds.",
)
@limiter.limit("60/minute")
async def health(request: Request, response: Response) -> HealthResponse:
    """Return current health status and uptime."""
    start: float = getattr(request.app.state, "start_time", time.time())
    uptime = round(time.time() - start, 1)
    return HealthResponse(
        data=HealthData(status="healthy", version="0.1.0", uptime=uptime)
    )


@router.post(
    "/power/sample-size",
    response_model=SampleSizeResponse,
    summary="Calculate required sample size",
    description=(
        "Given a baseline conversion rate and a minimum detectable effect, "
        "returns the per-group sample size needed to achieve the desired power, "
        "plus a 20-point power curve."
    ),
)
@limiter.limit("60/minute")
async def get_sample_size(
    request: Request,
    response: Response,
    body: SampleSizeRequest,
    engine: Annotated[StatsEngine, Depends(get_stats_engine)],
) -> SampleSizeResponse:
    """Compute required per-group sample size for a two-proportion A/B test."""
    req_id = get_request_id(request)
    logger.info(
        "sample-size req=%s baseline=%.4f mde=%.4f alpha=%.3f power=%.2f",
        req_id,
        body.baseline_rate,
        body.mde,
        body.alpha,
        body.power,
    )
    try:
        result = engine.compute_sample_size(
            baseline_rate=body.baseline_rate,
            mde=body.mde,
            alpha=body.alpha,
            power=body.power,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SampleSizeResponse(
        data=SampleSizeData(
            control_size=result.control_size,
            treatment_size=result.treatment_size,
            total_sample_size=result.total_sample_size,
            cohens_d=result.cohens_d,
            method_used=result.method_used,
            power_curve=[
                PowerCurvePoint(n=p["n"], power=p["power"]) for p in result.power_curve
            ],
        )
    )


@router.post(
    "/power/runtime",
    response_model=RuntimeResponse,
    summary="Estimate experiment runtime",
    description=(
        "Given a required total sample size and average daily traffic, "
        "returns expected experiment duration in days and weeks with a 95% CI."
    ),
)
@limiter.limit("60/minute")
async def get_runtime(
    request: Request,
    response: Response,
    body: RuntimeRequest,
    engine: Annotated[StatsEngine, Depends(get_stats_engine)],
) -> RuntimeResponse:
    """Estimate experiment duration using a Poisson traffic model."""
    req_id = get_request_id(request)
    logger.info(
        "runtime req=%s required_n=%d daily_traffic=%d",
        req_id,
        body.required_sample_size,
        body.daily_traffic,
    )
    try:
        result = engine.compute_runtime(
            required_sample_size=body.required_sample_size,
            daily_traffic=body.daily_traffic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RuntimeResponse(
        data=RuntimeData(
            days_expected=result.days_expected,
            days_lower_95=result.days_lower_95,
            days_upper_95=result.days_upper_95,
            weeks_expected=result.weeks_expected,
        )
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Run full experiment analysis",
    description=(
        "Runs the six-stage stats pipeline: power analysis, hypothesis test, "
        "optional O'Brien-Fleming sequential check, optional CUPED variance "
        "reduction, optional BH multiple-comparison correction, and an "
        "overall recommendation with a plain-English summary."
    ),
)
@limiter.limit("60/minute")
async def analyze(
    request: Request,
    response: Response,
    body: AnalyzeRequest,
    engine: Annotated[StatsEngine, Depends(get_stats_engine)],
) -> AnalyzeResponse:
    """Execute the full experiment analysis pipeline."""
    req_id = get_request_id(request)
    logger.info(
        "analyze req=%s test_type=%s control_n=%d treatment_n=%d",
        req_id,
        body.config.test_type,
        body.data.control_n,
        body.data.treatment_n,
    )

    try:
        config = ExperimentConfig(**body.config.model_dump())
        data = ExperimentData(**body.data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        analysis = engine.analyze(config, data, body.current_look)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return analysis_to_response(analysis)

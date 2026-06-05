"""Intelligence API router — /api/v1/intelligence/*.

Exposes Claude-powered experiment planning and result interpretation endpoints.
Rate limits: 10/minute for planning, 5/minute for streaming interpretation,
3/minute for report generation (most expensive endpoint),
30/minute for the usage monitoring endpoint.
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_request_id, limiter
from app.intelligence.interpreter import (
    PROMPT_VERSION,
    FullAnalysisResult,
    MLAnalysisSummary,
    build_fallback_interpretation,
    interpret_results,
    parse_ml_from_json,
    parse_stats_from_json,
)
from app.intelligence.planner import (
    ExperimentPlanResult,
    extract_clarifying_questions,
    plan_experiment,
)
from app.repositories.experiment_repo import get_experiment
from app.repositories.result_repo import get_latest_result

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


# ---------------------------------------------------------------------------
# Planning endpoint
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    description: str
    context: dict | None = None


@router.post(
    "/plan",
    response_model=ExperimentPlanResult,
    summary="Generate a structured experiment plan from a natural-language description",
    description=(
        "Calls the Claude API to extract a structured experiment plan from free text, "
        "then verifies all sample size recommendations against the Axiom stats engine. "
        "Returns either a complete plan or clarifying questions when the description "
        "is too vague to plan reliably."
    ),
)
@limiter.limit("10/minute")
async def create_plan(
    request: Request,
    response: Response,
    body: PlanRequest,
    db: AsyncSession = Depends(get_db),
) -> ExperimentPlanResult:
    """Generate a validated experiment plan or request clarification."""
    req_id = get_request_id(request)
    logger.info(
        "intelligence/plan req=%s description_len=%d",
        req_id,
        len(body.description),
    )

    try:
        result = await plan_experiment(
            description=body.description,
            context=body.context,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError:
        logger.warning(
            "intelligence/plan req=%s timed out — returning fallback questions", req_id
        )
        questions = await extract_clarifying_questions(body.description)
        return JSONResponse(
            status_code=504,
            content={
                "error": {
                    "code": "AI_TIMEOUT",
                    "message": "The AI service timed out. Please try again.",
                },
                "clarifying_questions": questions,
            },
        )
    except RuntimeError as exc:
        logger.error("intelligence/plan req=%s runtime error: %s", req_id, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return result


# ---------------------------------------------------------------------------
# SSE interpretation endpoint
# ---------------------------------------------------------------------------


async def _sse_chunks(
    stats_result: FullAnalysisResult,
    ml_result: MLAnalysisSummary,
    experiment_name: str,
    daily_traffic: int | None,
    experiment_id: UUID,
) -> AsyncGenerator[str, None]:
    """Generate SSE-formatted chunks from the Claude interpretation stream.

    On stream failure, emits a [FALLBACK] sentinel then switches to the
    template-based fallback (no additional API call). Logs the full
    assembled interpretation to ai_interactions when the stream completes.
    """
    assembled: list[str] = []
    stream_ok = False

    try:
        async for chunk in interpret_results(
            stats_result=stats_result,
            ml_result=ml_result,
            experiment_name=experiment_name,
            daily_traffic=daily_traffic,
        ):
            assembled.append(chunk)
            # Encode multi-line chunks as proper multi-line SSE so the browser
            # EventSource receives the full text in a single onmessage event.
            sse_data = chunk.replace("\n", "\ndata: ")
            yield f"data: {sse_data}\n\n"
        stream_ok = True

    except Exception as exc:
        logger.error(
            "SSE stream failed experiment_id=%s: %s",
            experiment_id,
            exc,
            exc_info=True,
        )
        fallback = build_fallback_interpretation(stats_result, ml_result)
        sse_data = fallback.replace("\n", "\ndata: ")
        yield f"data: {sse_data}\n\n"

    # Terminal sentinel lets the frontend close the EventSource cleanly
    # without triggering the onerror handler.
    yield "data: [DONE]\n\n"

    if stream_ok and assembled:
        full_text = "".join(assembled)
        await _log_interpretation(experiment_id, experiment_name, full_text)


async def _log_interpretation(
    experiment_id: UUID,
    experiment_name: str,
    full_text: str,
) -> None:
    """Write the completed interpretation to ai_interactions. Fails silently."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.experiment import AIInteraction, InteractionType

        async with AsyncSessionLocal() as session:
            record = AIInteraction(
                experiment_id=experiment_id,
                interaction_type=InteractionType.interpretation,
                user_prompt=experiment_name,
                ai_response=full_text,
                prompt_version=PROMPT_VERSION,
                duration_ms=None,
            )
            session.add(record)
            await session.commit()
            logger.info(
                "logged interpretation to ai_interactions experiment_id=%s chars=%d",
                experiment_id,
                len(full_text),
            )
    except Exception as exc:
        logger.warning(
            "failed to log interpretation experiment_id=%s: %s",
            experiment_id,
            exc,
        )


@router.get(
    "/experiments/{experiment_id}/interpret",
    summary="Stream an AI interpretation of experiment results as Server-Sent Events",
    description=(
        "Loads the experiment and its most recent analysis result from the database, "
        "then streams a Claude-generated plain-English interpretation as SSE. "
        "On stream failure, falls back to a template-based interpretation. "
        "Rate limited to 5 requests/minute per IP."
    ),
)
@limiter.limit("5/minute")
async def stream_interpretation(
    request: Request,
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream an AI interpretation of an experiment's results."""
    req_id = get_request_id(request)
    logger.info(
        "intelligence/interpret req=%s experiment_id=%s",
        req_id,
        experiment_id,
    )

    experiment = await get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "EXPERIMENT_NOT_FOUND",
                    "message": "Experiment not found",
                }
            },
        )

    result = await get_latest_result(db, experiment_id)
    if result is None or result.full_analysis_json is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "NO_RESULTS",
                    "message": "No analysis results found for this experiment",
                }
            },
        )

    json_data: dict = result.full_analysis_json
    stats_result = parse_stats_from_json(json_data)
    ml_result = parse_ml_from_json(json_data)

    logger.info(
        "starting interpretation stream experiment=%r significant=%s verdict=%s",
        experiment.name,
        stats_result.is_significant,
        ml_result.overall_verdict,
    )

    return StreamingResponse(
        _sse_chunks(
            stats_result=stats_result,
            ml_result=ml_result,
            experiment_name=experiment.name,
            daily_traffic=experiment.daily_traffic_estimate,
            experiment_id=experiment_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ---------------------------------------------------------------------------
# Report endpoint
# ---------------------------------------------------------------------------


class ReportRequest(BaseModel):
    format: Literal["markdown", "html"] = "markdown"
    daily_revenue: float | None = None


@router.post(
    "/experiments/{experiment_id}/report",
    summary="Generate an executive stakeholder report for an experiment",
    description=(
        "Loads the experiment and its most recent analysis result from the database, "
        "generates an 8-section stakeholder report using Claude (sections 1–7) and "
        "programmatic code (section 8), stores the markdown in experiment_results, "
        "and returns the full StakeholderReport. "
        "Rate limited to 3 requests/minute per IP — report generation is expensive."
    ),
)
@limiter.limit("3/minute")
async def generate_experiment_report(
    request: Request,
    experiment_id: UUID,
    body: ReportRequest = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Generate and store a stakeholder report for an experiment."""
    from app.intelligence.reporter import StakeholderReport, generate_report

    if body is None:
        body = ReportRequest()

    req_id = get_request_id(request)
    logger.info(
        "intelligence/report req=%s experiment_id=%s format=%s",
        req_id,
        experiment_id,
        body.format,
    )

    experiment = await get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "EXPERIMENT_NOT_FOUND",
                    "message": "Experiment not found",
                }
            },
        )

    result = await get_latest_result(db, experiment_id)
    if result is None or result.full_analysis_json is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "NO_RESULTS",
                    "message": "No analysis results found for this experiment",
                }
            },
        )

    json_data: dict = result.full_analysis_json
    stats_result = parse_stats_from_json(json_data)
    ml_result = parse_ml_from_json(json_data)

    logger.info(
        "generating report experiment=%r significant=%s verdict=%s",
        experiment.name,
        stats_result.is_significant,
        ml_result.overall_verdict,
    )

    report: StakeholderReport = await generate_report(
        experiment_name=experiment.name,
        stats_result=stats_result,
        ml_result=ml_result,
        daily_traffic=experiment.daily_traffic_estimate,
        daily_revenue=body.daily_revenue,
        format=body.format,
        db=db,
        experiment_id=experiment_id,
    )

    # Persist report markdown to the result row
    result.report_markdown = report.markdown_content
    await db.flush()

    # Serialise the dataclass to a dict for the JSON response
    response_data = {
        "data": {
            "title": report.title,
            "generated_at": report.generated_at.isoformat(),
            "prompt_version": report.prompt_version,
            "recommendation": report.recommendation,
            "confidence_level": report.confidence_level,
            "confidence_reasoning": report.confidence_reasoning,
            "key_metric": report.key_metric,
            "word_count": report.word_count,
            "ai_generated_sections": report.ai_generated_sections,
            "programmatic_sections": report.programmatic_sections,
            "sections": [
                {
                    "section_number": s.section_number,
                    "title": s.title,
                    "content": s.content,
                    "is_ai_generated": s.is_ai_generated,
                    "data_sources": s.data_sources,
                }
                for s in report.sections
            ],
            "markdown_content": report.markdown_content,
            "html_content": report.html_content,
        },
        "meta": {},
    }

    logger.info(
        "report complete experiment=%r recommendation=%s confidence=%s words=%d",
        experiment.name,
        report.recommendation,
        report.confidence_level,
        report.word_count,
    )

    return JSONResponse(content=response_data)


# ---------------------------------------------------------------------------
# Usage / cost monitoring endpoint
# ---------------------------------------------------------------------------


def _empty_period() -> dict:
    return {
        "total_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "fallback_rate": 0.0,
        "by_function": {},
    }


def _build_period(rows: list) -> dict:
    """Aggregate a list of per-function DB rows into a period summary dict."""
    total_calls = 0
    total_input = 0
    total_output = 0
    total_cost = 0.0
    total_fallback = 0
    by_function: dict = {}

    for row in rows:
        fn = row.interaction_type
        calls = row.calls or 0
        inp = row.total_input or 0
        out = row.total_output or 0
        cost = float(row.total_cost or 0.0)
        avg_ms = int(row.avg_latency or 0)
        fallback = row.fallback_calls or 0

        total_calls += calls
        total_input += inp
        total_output += out
        total_cost += cost
        total_fallback += fallback

        by_function[fn] = {
            "calls": calls,
            "cost": round(cost, 6),
            "avg_latency_ms": avg_ms,
        }

    fallback_rate = round(total_fallback / total_calls, 4) if total_calls else 0.0

    return {
        "total_calls": total_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_usd": round(total_cost, 6),
        "fallback_rate": fallback_rate,
        "by_function": by_function,
    }


@router.get(
    "/usage",
    summary="Claude API usage and cost summary",
    description=(
        "Returns aggregated token usage, estimated cost, and latency statistics "
        "for all Claude API calls recorded in ai_interactions. "
        "Broken down by time period (today / all time) and by function "
        "(planner / interpreter / reporter). "
        "Rate limited to 30 requests/minute — this is a monitoring endpoint."
    ),
)
@limiter.limit("30/minute")
async def get_usage(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return Claude API usage statistics and estimated cost."""
    from app.models.experiment import AIInteraction

    today_start = datetime.now(tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    agg_cols = (
        AIInteraction.interaction_type,
        func.count().label("calls"),
        func.sum(AIInteraction.input_tokens).label("total_input"),
        func.sum(AIInteraction.output_tokens).label("total_output"),
        func.sum(AIInteraction.estimated_cost_usd).label("total_cost"),
        func.avg(AIInteraction.duration_ms).label("avg_latency"),
        func.count()
        .filter(AIInteraction.status == "fallback_used")
        .label("fallback_calls"),
    )

    today_rows = (
        await db.execute(
            select(*agg_cols)
            .where(AIInteraction.created_at >= today_start)
            .group_by(AIInteraction.interaction_type)
        )
    ).all()

    all_rows = (
        await db.execute(select(*agg_cols).group_by(AIInteraction.interaction_type))
    ).all()

    return JSONResponse(
        content={
            "data": {
                "today": _build_period(today_rows) if today_rows else _empty_period(),
                "all_time": _build_period(all_rows) if all_rows else _empty_period(),
            },
            "meta": {},
        }
    )

"""Intelligence API router — /api/v1/intelligence/*.

Exposes Claude-powered experiment planning endpoints.
Rate limit: 10 requests/minute per IP (Claude calls are expensive).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_request_id, limiter
from app.intelligence.planner import (
    ExperimentPlanResult,
    extract_clarifying_questions,
    plan_experiment,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


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
        logger.warning("intelligence/plan req=%s timed out — returning fallback questions", req_id)
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

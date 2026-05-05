"""Repository for ExperimentResult storage and retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.engine import MLAnalysisResult
from app.models.experiment import AnalysisType, ExperimentResult


def _serialize_ml_result(result: MLAnalysisResult) -> dict:
    """Convert an MLAnalysisResult to a JSON-serializable dict for JSONB storage.

    Only the verdict-level fields are stored; large numpy arrays (ITEs) are
    intentionally omitted to keep the column size bounded.

    Args:
        result: Completed ML analysis result.

    Returns:
        JSON-serializable dict safe for PostgreSQL JSONB.
    """
    return {
        "overall_verdict": result.overall_verdict,
        "key_insights": result.key_insights,
        "capability_report": [
            {
                "module": s.module,
                "status": s.status,
                "skip_reason": s.skip_reason,
                "duration_seconds": s.duration_seconds,
            }
            for s in result.capability_report
        ],
        "can_trust_results": result.can_trust_results,
        "recommendation": result.recommendation,
    }


async def store_result(
    db: AsyncSession,
    experiment_id: UUID,
    ml_result: MLAnalysisResult,
) -> ExperimentResult:
    """Persist an ML analysis result linked to an experiment.

    Args:
        db: Active async session.
        experiment_id: Experiment the result belongs to.
        ml_result: Completed ML analysis.

    Returns:
        The newly created ExperimentResult row.
    """
    record = ExperimentResult(
        experiment_id=experiment_id,
        analysis_type=AnalysisType.full,
        full_analysis_json=_serialize_ml_result(ml_result),
        is_significant=ml_result.can_trust_results,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def get_latest_result(
    db: AsyncSession,
    experiment_id: UUID,
) -> ExperimentResult | None:
    """Return the most recent analysis result for an experiment.

    Args:
        db: Active async session.
        experiment_id: Experiment to look up.

    Returns:
        Most recent ExperimentResult, or None if no results exist.
    """
    result = await db.execute(
        select(ExperimentResult)
        .where(ExperimentResult.experiment_id == experiment_id)
        .order_by(ExperimentResult.analyzed_at.desc())
        .limit(1)
    )
    return result.scalars().first()

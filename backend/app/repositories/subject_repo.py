"""Repository for ExperimentSubject storage and retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import ExperimentSubject


async def bulk_insert_subjects(
    db: AsyncSession,
    experiment_id: UUID,
    rows: list[dict],
) -> int:
    """Insert subject rows, skipping duplicates via ON CONFLICT DO NOTHING.

    Args:
        db: Active async session.
        experiment_id: Experiment the subjects belong to.
        rows: List of dicts with keys: subject_id, variant, outcome,
            covariates. experiment_id is injected here, not by caller.

    Returns:
        Number of rows actually inserted (excludes skipped duplicates).
    """
    if not rows:
        return 0
    for row in rows:
        row["experiment_id"] = experiment_id
    stmt = pg_insert(ExperimentSubject).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["experiment_id", "subject_id"]
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


async def get_subjects_for_experiment(
    db: AsyncSession,
    experiment_id: UUID,
) -> list[ExperimentSubject]:
    """Return all subjects for an experiment ordered by variant then uploaded_at.

    Args:
        db: Active async session.
        experiment_id: Experiment to query.

    Returns:
        List of ExperimentSubject rows, control group first.
    """
    result = await db.execute(
        select(ExperimentSubject)
        .where(ExperimentSubject.experiment_id == experiment_id)
        .order_by(ExperimentSubject.variant, ExperimentSubject.uploaded_at)
    )
    return list(result.scalars().all())


async def has_subject_data(
    db: AsyncSession,
    experiment_id: UUID,
) -> bool:
    """Return True if the experiment has at least one uploaded subject row.

    Args:
        db: Active async session.
        experiment_id: Experiment to check.

    Returns:
        True if any subjects exist for this experiment.
    """
    result = await db.execute(
        select(func.count())
        .select_from(ExperimentSubject)
        .where(ExperimentSubject.experiment_id == experiment_id)
    )
    return (result.scalar() or 0) > 0


async def get_subject_counts(
    db: AsyncSession,
    experiment_id: UUID,
) -> dict:
    """Return subject counts by variant for an experiment.

    Args:
        db: Active async session.
        experiment_id: Experiment to count.

    Returns:
        Dict with total, control, treatment counts.
    """
    result = await db.execute(
        select(
            ExperimentSubject.variant,
            func.count().label("count"),
        )
        .where(ExperimentSubject.experiment_id == experiment_id)
        .group_by(ExperimentSubject.variant)
    )
    rows = result.all()
    counts = {row.variant: row.count for row in rows}
    control = counts.get(0, 0)
    treatment = counts.get(1, 0)
    return {
        "total": control + treatment,
        "control": control,
        "treatment": treatment,
    }

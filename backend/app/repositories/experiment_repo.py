"""Repository for Experiment CRUD operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import Experiment, ExperimentStatus, ExperimentType
from app.schemas.ml import ExperimentCreate


async def create_experiment(db: AsyncSession, data: ExperimentCreate) -> Experiment:
    """Insert a new experiment row and return the persisted object.

    Args:
        db: Active async session.
        data: Validated creation payload.

    Returns:
        The newly created Experiment with all server-generated fields populated.
    """
    exp = Experiment(
        name=data.name,
        description=data.description,
        hypothesis=data.hypothesis,
        status=ExperimentStatus.draft,
        experiment_type=ExperimentType(data.experiment_type),
        baseline_metric=data.baseline_metric,
        mde=data.mde,
        alpha=data.alpha,
        power=data.power,
        daily_traffic_estimate=data.daily_traffic_estimate,
    )
    db.add(exp)
    await db.flush()
    await db.refresh(exp)
    return exp


async def get_experiment(db: AsyncSession, experiment_id: UUID) -> Experiment | None:
    """Return the experiment with the given id, or None if not found.

    Args:
        db: Active async session.
        experiment_id: Primary key to look up.

    Returns:
        Experiment instance or None.
    """
    return await db.get(Experiment, experiment_id)


async def list_experiments(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Experiment], int]:
    """Return a paginated list of experiments (newest first) and the total count.

    Args:
        db: Active async session.
        page: 1-based page number.
        page_size: Rows per page (max 100).

    Returns:
        Tuple of (experiments slice, total row count).
    """
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(Experiment))
    total: int = total_result.scalar() or 0
    rows_result = await db.execute(
        select(Experiment)
        .order_by(Experiment.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(rows_result.scalars().all()), total


async def update_status(
    db: AsyncSession,
    experiment_id: UUID,
    status: str,
) -> Experiment | None:
    """Update an experiment's status field.

    Args:
        db: Active async session.
        experiment_id: Experiment to update.
        status: New status string ("running" | "completed" | "stopped_early").

    Returns:
        Updated Experiment, or None if not found.
    """
    exp = await db.get(Experiment, experiment_id)
    if exp is None:
        return None
    exp.status = ExperimentStatus(status)
    await db.flush()
    return exp

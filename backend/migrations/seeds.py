"""Seed the database with three realistic sample experiments.

Usage (inside container):
    docker compose exec backend python /app/backend/migrations/seeds.py

Safe to re-run — checks by experiment name before inserting each one.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.experiment import (
    Experiment,
    ExperimentMetric,
    ExperimentStatus,
    ExperimentType,
    MetricType,
)


async def _exists(session: AsyncSession, name: str) -> bool:
    row = await session.scalar(select(Experiment).where(Experiment.name == name))
    return row is not None


async def seed(session: AsyncSession) -> None:
    """Insert each seed experiment if it doesn't already exist by name."""
    created = 0

    # ── Experiment 1: E-Commerce Checkout Redesign ─────────────────────────
    name1 = "E-Commerce Checkout Redesign"
    if await _exists(session, name1):
        print(f"  Skipping {name1!r} — already exists.")
    else:
        exp1 = Experiment(
            name=name1,
            description=(
                "Testing a simplified single-page checkout against the current "
                "multi-step flow to improve end-of-funnel conversion rate."
            ),
            status=ExperimentStatus.running,
            experiment_type=ExperimentType.proportion,
            hypothesis=(
                "Simplifying checkout to a single page will increase conversion "
                "rate by at least 1 pp (20% relative lift from 5% baseline)."
            ),
            baseline_metric=0.05,
            mde=0.01,
            alpha=0.05,
            power=0.80,
            daily_traffic_estimate=10000,
            started_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        session.add(exp1)
        await session.flush()
        session.add_all([
            ExperimentMetric(
                experiment_id=exp1.id,
                metric_name="conversion_rate",
                metric_type=MetricType.primary,
                is_primary=True,
            ),
            ExperimentMetric(
                experiment_id=exp1.id,
                metric_name="revenue_per_session",
                metric_type=MetricType.secondary,
                is_primary=False,
            ),
            ExperimentMetric(
                experiment_id=exp1.id,
                metric_name="cart_abandonment_rate",
                metric_type=MetricType.guardrail,
                is_primary=False,
            ),
        ])
        print(f"  Created {name1!r}  id={exp1.id}")
        created += 1

    # ── Experiment 2: SaaS Onboarding Checklist ────────────────────────────
    name2 = "SaaS Onboarding Checklist"
    if await _exists(session, name2):
        print(f"  Skipping {name2!r} — already exists.")
    else:
        exp2 = Experiment(
            name=name2,
            description=(
                "Adding an interactive onboarding checklist to the trial dashboard "
                "to guide new users toward activation milestones."
            ),
            status=ExperimentStatus.running,
            experiment_type=ExperimentType.mean,
            hypothesis=(
                "An interactive checklist will increase activation score by "
                "1.5 points, with heterogeneous effects by company size."
            ),
            baseline_metric=26.0,
            mde=1.5,
            alpha=0.05,
            power=0.80,
            daily_traffic_estimate=5000,
            started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        )
        session.add(exp2)
        await session.flush()
        session.add_all([
            ExperimentMetric(
                experiment_id=exp2.id,
                metric_name="trial_to_paid_rate",
                metric_type=MetricType.primary,
                is_primary=True,
            ),
            ExperimentMetric(
                experiment_id=exp2.id,
                metric_name="time_to_first_value",
                metric_type=MetricType.secondary,
                is_primary=False,
            ),
            ExperimentMetric(
                experiment_id=exp2.id,
                metric_name="support_tickets",
                metric_type=MetricType.guardrail,
                is_primary=False,
            ),
        ])
        print(f"  Created {name2!r}  id={exp2.id}")
        created += 1

    # ── Experiment 3: Marketplace Fee Reduction ────────────────────────────
    # mean test; baseline GMV $45/seller, treatment target $50 ($5 absolute lift)
    # mde=5.0 stored as absolute dollar value; analyze endpoint uses absolute lift.
    name3 = "Marketplace Fee Reduction"
    if await _exists(session, name3):
        print(f"  Skipping {name3!r} — already exists.")
    else:
        exp3 = Experiment(
            name=name3,
            description=(
                "Reducing the seller transaction fee from 8% to 5% to test "
                "whether lower fees drive increased GMV per active seller."
            ),
            status=ExperimentStatus.running,
            experiment_type=ExperimentType.mean,
            hypothesis=(
                "Reducing the fee will increase avg GMV per seller by $5 "
                "(11% relative lift), possibly with a novelty decay in the first "
                "two weeks as sellers adjust behaviour."
            ),
            baseline_metric=45.0,
            mde=5.0,
            alpha=0.05,
            power=0.80,
            daily_traffic_estimate=8000,
            started_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        session.add(exp3)
        await session.flush()
        session.add_all([
            ExperimentMetric(
                experiment_id=exp3.id,
                metric_name="gmv_per_seller",
                metric_type=MetricType.primary,
                is_primary=True,
            ),
            ExperimentMetric(
                experiment_id=exp3.id,
                metric_name="listings_created",
                metric_type=MetricType.secondary,
                is_primary=False,
            ),
            ExperimentMetric(
                experiment_id=exp3.id,
                metric_name="seller_retention",
                metric_type=MetricType.guardrail,
                is_primary=False,
            ),
        ])
        print(f"  Created {name3!r}  id={exp3.id}")
        created += 1

    if created:
        await session.commit()
        print(f"Seed complete — {created} new experiment(s) created.")
    else:
        print("All seed experiments already present — nothing to do.")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        print("Checking seed experiments…")
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())

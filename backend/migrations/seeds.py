"""Seed the database with three realistic sample experiments.

Usage (inside container):
    docker compose exec backend python /app/backend/migrations/seeds.py

Safe to re-run — exits cleanly if experiments already exist.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.experiment import (
    Experiment,
    ExperimentMetric,
    ExperimentStatus,
    ExperimentType,
    MetricType,
)


async def seed(session: AsyncSession) -> None:
    """Insert three realistic experiments with metric definitions."""

    # ── Experiment 1: E-Commerce Checkout Redesign ─────────────────────────
    # proportion test; baseline 5%, treatment target 6% (1 pp absolute lift)
    exp1 = Experiment(
        name="E-Commerce Checkout Redesign",
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
    print(f"  exp1 id={exp1.id}  [{exp1.name!r}]")

    # ── Experiment 2: SaaS Onboarding Checklist ────────────────────────────
    # proportion test; baseline 12%, treatment target 14% (2 pp absolute lift)
    # HTE story: large companies respond much better than small ones.
    exp2 = Experiment(
        name="SaaS Onboarding Checklist",
        description=(
            "Adding an interactive onboarding checklist to the trial dashboard "
            "to guide new users toward activation milestones."
        ),
        status=ExperimentStatus.running,
        experiment_type=ExperimentType.proportion,
        hypothesis=(
            "An interactive checklist will increase trial-to-paid conversion by "
            "2 pp, with heterogeneous effects by company size."
        ),
        baseline_metric=0.12,
        mde=0.02,
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
    print(f"  exp2 id={exp2.id}  [{exp2.name!r}]")

    # ── Experiment 3: Marketplace Fee Reduction ────────────────────────────
    # mean test; baseline GMV $45/seller, treatment target $50 ($5 absolute lift)
    # mde=5.0 stored as absolute dollar value (bypasses API schema constraint).
    # The analyze endpoint interprets mde as absolute for mean experiments.
    exp3 = Experiment(
        name="Marketplace Fee Reduction",
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
    print(f"  exp3 id={exp3.id}  [{exp3.name!r}]")

    await session.commit()
    print("Seed complete — 3 experiments, 9 metrics.")


async def main() -> None:
    from sqlalchemy import func, select

    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Experiment))
        if count:
            print(f"Database already has {count} experiment(s) — skipping seed.")
            return
        print("Seeding database…")
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())

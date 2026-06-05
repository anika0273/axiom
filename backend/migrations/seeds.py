"""Seed the database with one complete sample experiment.

Usage (inside container):
    docker compose exec backend python /app/backend/migrations/seeds.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.experiment import (
    AIInteraction,
    AnalysisType,
    Experiment,
    ExperimentMetric,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    InteractionType,
    MetricType,
)


async def seed(session: AsyncSession) -> None:
    """Insert one sample experiment with result, metrics, and AI interaction."""
    experiment = Experiment(
        name="Homepage CTA Button Color Test",
        description=(
            "Testing whether a green CTA button outperforms the current blue "
            "button on homepage conversion rate."
        ),
        status=ExperimentStatus.completed,
        experiment_type=ExperimentType.proportion,
        hypothesis=(
            "A green CTA button will increase homepage conversion by at least "
            "5% relative to the current blue button."
        ),
        baseline_metric=0.032,
        mde=0.003,
        alpha=0.05,
        power=0.80,
        daily_traffic_estimate=5000,
        started_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    session.add(experiment)
    await session.flush()

    result = ExperimentResult(
        experiment_id=experiment.id,
        analysis_type=AnalysisType.full,
        full_analysis_json={
            "control": {"n": 35021, "conversions": 1121, "rate": 0.032},
            "treatment": {"n": 34978, "conversions": 1259, "rate": 0.036},
            "z_score": 3.87,
            "p_value": 0.00011,
            "confidence_interval": [0.0024, 0.0056],
            "relative_lift": 0.125,
        },
        is_significant=True,
        p_value=0.00011,
        relative_lift=0.125,
    )
    session.add(result)

    metrics = [
        ExperimentMetric(
            experiment_id=experiment.id,
            metric_name="homepage_conversion_rate",
            metric_type=MetricType.primary,
            is_primary=True,
        ),
        ExperimentMetric(
            experiment_id=experiment.id,
            metric_name="page_load_time_p95",
            metric_type=MetricType.guardrail,
            is_primary=False,
        ),
        ExperimentMetric(
            experiment_id=experiment.id,
            metric_name="bounce_rate",
            metric_type=MetricType.secondary,
            is_primary=False,
        ),
    ]
    session.add_all(metrics)

    ai_log = AIInteraction(
        experiment_id=experiment.id,
        interaction_type=InteractionType.interpretation,
        user_prompt="Interpret the results of the CTA button color experiment.",
        ai_response=(
            "The green CTA button shows a statistically significant lift of 12.5% "
            "in homepage conversion rate (p=0.00011, well below α=0.05). With 70,000 "
            "subjects split evenly, this result has high statistical power. "
            "Recommendation: ship the green button — the effect size exceeds the MDE "
            "and the guardrail metrics are clean."
        ),
        tokens_used=312,
    )
    session.add(ai_log)

    await session.commit()

    print(f"Seeded experiment id : {experiment.id}")
    print(f"  status             : {experiment.status.value}")
    print(f"  result significant : {result.is_significant}  (p={result.p_value})")
    print(f"  relative lift      : {result.relative_lift:.1%}")
    print(f"  metrics            : {[m.metric_name for m in metrics]}")
    print(f"  AI tokens used     : {ai_log.tokens_used}")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())

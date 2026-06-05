"""Analysis service — orchestrates stats + ML engines and DB persistence."""

from __future__ import annotations

from uuid import UUID

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.engine import MLExperimentInput, run_ml_analysis
from app.repositories import result_repo
from app.schemas.ml import (
    DailyMetricRecord,
    MLAnalysisRequest,
    MLAnalysisResultData,
    ModuleStatusOut,
)


def _build_result_data(
    ml_result,
    experiment_id: UUID | None = None,
    stored_id: UUID | None = None,
) -> MLAnalysisResultData:
    """Translate an MLAnalysisResult dataclass into the Pydantic response model.

    Args:
        ml_result: Completed MLAnalysisResult from the engine.
        experiment_id: Optional experiment this analysis belongs to.
        stored_id: DB primary key of the persisted ExperimentResult row, if any.

    Returns:
        MLAnalysisResultData ready for the API response envelope.
    """
    return MLAnalysisResultData(
        overall_verdict=ml_result.overall_verdict,
        key_insights=ml_result.key_insights,
        capability_report=[
            ModuleStatusOut(
                module=s.module,
                status=s.status,
                skip_reason=s.skip_reason,
                duration_seconds=s.duration_seconds,
            )
            for s in ml_result.capability_report
        ],
        can_trust_results=ml_result.can_trust_results,
        recommendation=ml_result.recommendation,
        experiment_id=experiment_id,
        result_id=stored_id,
    )


def _daily_records_to_df(records: list[DailyMetricRecord]) -> pd.DataFrame:
    df = pd.DataFrame([r.model_dump() for r in records])
    df["date"] = pd.to_datetime(df["date"])
    return df


async def run_analysis(
    body: MLAnalysisRequest,
    db: AsyncSession | None = None,
) -> MLAnalysisResultData:
    """Run the ML analysis pipeline and optionally persist the result.

    Converts the request payload into the data structures expected by the ML
    engine, executes all four modules (anomaly, novelty, HTE, segments), and —
    when experiment_id is provided and a db session is available — stores the
    result in experiment_results.

    Args:
        body: Validated ML analysis request.
        db: Async session used to persist the result. Pass None (or omit
            experiment_id in body) to skip persistence.

    Returns:
        MLAnalysisResultData with verdict, insights, capability report,
        and optional experiment_id / result_id references.

    Raises:
        ValueError: Propagated from run_ml_analysis when group sizes are too small.
    """
    daily_df = _daily_records_to_df(body.daily_metrics) if body.daily_metrics else None
    user_features = pd.DataFrame(body.user_features) if body.user_features else None

    experiment_input = MLExperimentInput(
        control_values=body.control_values,
        treatment_values=body.treatment_values,
        user_features=user_features,
        daily_metrics=daily_df,
    )

    ml_result = run_ml_analysis(experiment_input)

    stored_id: UUID | None = None
    if body.experiment_id is not None and db is not None:
        stored = await result_repo.store_result(db, body.experiment_id, ml_result)
        stored_id = stored.id

    return _build_result_data(
        ml_result, experiment_id=body.experiment_id, stored_id=stored_id
    )

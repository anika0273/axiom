"""ORM models for experiments, results, metrics, and AI interactions."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Enum as SAEnum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


# ── Enum definitions ──────────────────────────────────────────────────────────

class ExperimentStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    completed = "completed"
    stopped_early = "stopped_early"


class ExperimentType(str, enum.Enum):
    proportion = "proportion"
    mean = "mean"
    ratio = "ratio"


class AnalysisType(str, enum.Enum):
    full = "full"
    sequential_check = "sequential_check"
    interim = "interim"


class MetricType(str, enum.Enum):
    primary = "primary"
    secondary = "secondary"
    guardrail = "guardrail"


class InteractionType(str, enum.Enum):
    plan = "plan"
    interpretation = "interpretation"
    report = "report"


# ── ORM models ────────────────────────────────────────────────────────────────

class Experiment(Base):
    """Stores experiment configuration and lifecycle state."""

    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "(completed_at IS NULL OR started_at IS NULL OR completed_at > started_at)",
            name="ck_experiments_completed_after_started",
        ),
        Index("ix_experiments_status", "status"),
        Index("ix_experiments_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[ExperimentStatus] = mapped_column(
        SAEnum(ExperimentStatus, name="experiment_status", create_type=False),
        nullable=False,
    )
    experiment_type: Mapped[ExperimentType] = mapped_column(
        SAEnum(ExperimentType, name="experiment_type", create_type=False),
        nullable=False,
    )
    hypothesis: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    baseline_metric: Mapped[float] = mapped_column(sa.Float, nullable=False)
    mde: Mapped[float] = mapped_column(sa.Float, nullable=False)
    alpha: Mapped[float] = mapped_column(sa.Float, nullable=False, server_default="0.05")
    power: Mapped[float] = mapped_column(sa.Float, nullable=False, server_default="0.80")
    daily_traffic_estimate: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )

    results: Mapped[list[ExperimentResult]] = relationship(
        "ExperimentResult", back_populates="experiment", cascade="all, delete-orphan"
    )
    metrics: Mapped[list[ExperimentMetric]] = relationship(
        "ExperimentMetric", back_populates="experiment", cascade="all, delete-orphan"
    )
    ai_interactions: Mapped[list[AIInteraction]] = relationship(
        "AIInteraction", back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentResult(Base):
    """Statistical analysis output for one analysis run of an experiment."""

    __tablename__ = "experiment_results"
    __table_args__ = (
        Index("ix_experiment_results_experiment_id", "experiment_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_type: Mapped[AnalysisType] = mapped_column(
        SAEnum(AnalysisType, name="analysis_type", create_type=False),
        nullable=False,
    )
    full_analysis_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    is_significant: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    p_value: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    relative_lift: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    report_markdown: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="results")


class ExperimentMetric(Base):
    """Metric tracked for an experiment (primary, secondary, or guardrail)."""

    __tablename__ = "experiment_metrics"
    __table_args__ = (
        Index("ix_experiment_metrics_experiment_id", "experiment_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    metric_type: Mapped[MetricType] = mapped_column(
        SAEnum(MetricType, name="metric_type", create_type=False),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="false"
    )

    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="metrics")


class AIInteraction(Base):
    """Log of Claude API calls associated with experiment analysis."""

    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_interactions_experiment_id", "experiment_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    experiment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=True,
    )
    interaction_type: Mapped[InteractionType] = mapped_column(
        SAEnum(InteractionType, name="interaction_type", create_type=False),
        nullable=False,
    )
    user_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    ai_response: Mapped[str] = mapped_column(sa.Text, nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    # Phase 3 metadata columns (migration 002)
    prompt_version: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    confidence: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    experiment: Mapped[Experiment | None] = relationship(
        "Experiment", back_populates="ai_interactions"
    )

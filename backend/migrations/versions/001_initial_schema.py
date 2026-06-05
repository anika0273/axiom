"""Initial schema: experiments, results, metrics, ai_interactions.

Revision ID: 001
Revises:
Create Date: 2026-05-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types (must exist before tables) ─────────────────────────────────
    op.execute(
        "CREATE TYPE experiment_status AS ENUM "
        "('draft', 'running', 'completed', 'stopped_early')"
    )
    op.execute("CREATE TYPE experiment_type AS ENUM ('proportion', 'mean', 'ratio')")
    op.execute(
        "CREATE TYPE analysis_type AS ENUM ('full', 'sequential_check', 'interim')"
    )
    op.execute("CREATE TYPE metric_type AS ENUM ('primary', 'secondary', 'guardrail')")
    op.execute(
        "CREATE TYPE interaction_type AS ENUM ('plan', 'interpretation', 'report')"
    )

    # ── experiments ───────────────────────────────────────────────────────────
    op.create_table(
        "experiments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            PG_ENUM(name="experiment_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "experiment_type",
            PG_ENUM(name="experiment_type", create_type=False),
            nullable=False,
        ),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("baseline_metric", sa.Float(), nullable=False),
        sa.Column("mde", sa.Float(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False, server_default=sa.text("0.05")),
        sa.Column("power", sa.Float(), nullable=False, server_default=sa.text("0.80")),
        sa.Column("daily_traffic_estimate", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_experiments"),
        sa.CheckConstraint(
            "(completed_at IS NULL OR started_at IS NULL OR completed_at > started_at)",
            name="ck_experiments_completed_after_started",
        ),
    )
    op.create_index("ix_experiments_status", "experiments", ["status"])
    op.create_index("ix_experiments_created_at", "experiments", ["created_at"])

    # ── experiment_results ────────────────────────────────────────────────────
    op.create_table(
        "experiment_results",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_type",
            PG_ENUM(name="analysis_type", create_type=False),
            nullable=False,
        ),
        sa.Column("full_analysis_json", JSONB(), nullable=True),
        sa.Column("is_significant", sa.Boolean(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("relative_lift", sa.Float(), nullable=True),
        sa.Column(
            "analyzed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experiment_results"),
    )
    op.create_index(
        "ix_experiment_results_experiment_id",
        "experiment_results",
        ["experiment_id"],
    )

    # ── experiment_metrics ────────────────────────────────────────────────────
    op.create_table(
        "experiment_metrics",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_name", sa.Text(), nullable=False),
        sa.Column(
            "metric_type",
            PG_ENUM(name="metric_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experiment_metrics"),
    )
    op.create_index(
        "ix_experiment_metrics_experiment_id",
        "experiment_metrics",
        ["experiment_id"],
    )

    # ── ai_interactions ───────────────────────────────────────────────────────
    op.create_table(
        "ai_interactions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "interaction_type",
            PG_ENUM(name="interaction_type", create_type=False),
            nullable=False,
        ),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("ai_response", sa.Text(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_interactions"),
    )
    op.create_index(
        "ix_ai_interactions_experiment_id",
        "ai_interactions",
        ["experiment_id"],
    )


def downgrade() -> None:
    op.drop_table("ai_interactions")
    op.drop_table("experiment_metrics")
    op.drop_table("experiment_results")
    op.drop_table("experiments")
    op.execute("DROP TYPE IF EXISTS interaction_type")
    op.execute("DROP TYPE IF EXISTS metric_type")
    op.execute("DROP TYPE IF EXISTS analysis_type")
    op.execute("DROP TYPE IF EXISTS experiment_type")
    op.execute("DROP TYPE IF EXISTS experiment_status")

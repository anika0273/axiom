"""Add experiment_subjects table for subject-level CSV upload.

Revision ID: 005
Revises: 004
Create Date: 2026-06-06

Each row is one subject (user/device) assigned to a variant in an
experiment, with their outcome metric value and any additional
covariate columns from the CSV stored as JSONB.

The unique constraint on (experiment_id, subject_id) prevents the same
subject from being uploaded twice for the same experiment.  The compound
index on (experiment_id, variant) speeds up the per-variant aggregation
queries that feed the stats engine.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_subjects",
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
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("variant", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.Float(), nullable=False),
        sa.Column("covariates", JSONB(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experiment_subjects"),
    )
    op.create_index(
        "ix_experiment_subjects_experiment_id",
        "experiment_subjects",
        ["experiment_id"],
    )
    op.create_index(
        "ix_experiment_subjects_experiment_variant",
        "experiment_subjects",
        ["experiment_id", "variant"],
    )
    op.create_unique_constraint(
        "uq_experiment_subjects_experiment_subject",
        "experiment_subjects",
        ["experiment_id", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_experiment_subjects_experiment_variant",
        table_name="experiment_subjects",
    )
    op.drop_index(
        "ix_experiment_subjects_experiment_id",
        table_name="experiment_subjects",
    )
    op.drop_constraint(
        "uq_experiment_subjects_experiment_subject",
        "experiment_subjects",
        type_="unique",
    )
    op.drop_table("experiment_subjects")

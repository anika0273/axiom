"""Add report_markdown column to experiment_results for Phase 3 reporter.

Revision ID: 003
Revises: 002
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiment_results",
        sa.Column("report_markdown", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiment_results", "report_markdown")

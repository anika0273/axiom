"""Add status column to ai_interactions for call outcome tracking.

Revision ID: 004
Revises: 003
Create Date: 2026-05-06

Possible values: success | retry_success | fallback_used | failed
NULL on existing rows (pre-Phase-3 data where status was not tracked).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_interactions",
        sa.Column("status", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_interactions", "status")

"""Add metadata columns to ai_interactions for Phase 3 Claude API logging.

Revision ID: 002
Revises: 001
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_interactions", sa.Column("prompt_version", sa.Text, nullable=True))
    op.add_column("ai_interactions", sa.Column("input_tokens", sa.Integer, nullable=True))
    op.add_column("ai_interactions", sa.Column("output_tokens", sa.Integer, nullable=True))
    op.add_column("ai_interactions", sa.Column("estimated_cost_usd", sa.Float, nullable=True))
    op.add_column("ai_interactions", sa.Column("confidence", sa.Text, nullable=True))
    op.add_column("ai_interactions", sa.Column("duration_ms", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("ai_interactions", "duration_ms")
    op.drop_column("ai_interactions", "confidence")
    op.drop_column("ai_interactions", "estimated_cost_usd")
    op.drop_column("ai_interactions", "output_tokens")
    op.drop_column("ai_interactions", "input_tokens")
    op.drop_column("ai_interactions", "prompt_version")

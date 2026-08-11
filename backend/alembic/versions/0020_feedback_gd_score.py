"""feedback GD score

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-11

``session_feedback.score`` — the per-session GD score as JSON: composite
0-100, five pillar scores, the deterministic subscores and LLM rubric
integers behind them, ``rubric_version`` and the scoring model. Old rows stay
NULL; scores exist only for reports generated after this ships.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_feedback", sa.Column("score", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("session_feedback", "score")

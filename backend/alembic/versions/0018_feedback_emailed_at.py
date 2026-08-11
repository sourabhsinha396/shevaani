"""feedback emailed_at

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-11

When a report was last emailed to its learner — what lets the review UI's
"email feedback" button say "sent" instead of quietly allowing doubles.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "session_feedback",
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_feedback", "emailed_at")

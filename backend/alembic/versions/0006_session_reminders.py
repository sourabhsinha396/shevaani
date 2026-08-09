"""session reminders

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-08

One row per (session, offset), written *before* the emails go out and protected
by a unique constraint. That ordering is the point: two workers racing on the
same session both see it as un-reminded, both try to claim it, and only one wins
the insert. The loser sends nothing.

Nothing is backfilled. Sessions that already exist have no reminder rows, so the
first run after this migration would consider them all due — which is why the
job also bounds how late a reminder may be. A session starting in three days is
not due for its 24-hour reminder yet, and one that started yesterday is outside
the tolerance and will never be picked up.

`ON DELETE CASCADE`: these rows describe a session and have no meaning without
it. They are not the audit trail for money, so nothing here is worth keeping
after the session is gone.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hours_before", sa.SmallInteger(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_session_reminders_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_reminders")),
        sa.UniqueConstraint(
            "session_id", "hours_before", name="uq_session_reminders_session_hours"
        ),
    )
    op.create_index(
        op.f("ix_session_reminders_session_id"),
        "session_reminders",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_session_reminders_session_id"), table_name="session_reminders")
    op.drop_table("session_reminders")

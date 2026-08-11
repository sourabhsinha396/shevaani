"""session slugs + structured feedback

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-11

Two things:

* ``sessions.slug`` — human-readable URL identity (``/discussions/tuesday-
  debate-club`` instead of a UUID). Backfilled from titles, oldest first, so
  the plain slug goes to the session that has carried the title longest and
  repeats get ``-2``, ``-3``…

* ``session_feedback.structured`` — the model's answer kept as JSON instead of
  only the rendered markdown, so the frontend can lay the report out section
  by section. Old rows stay NULL and keep rendering from ``report_md``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _slugify(text: str) -> str:
    # Mirrors app/services/slugs.py::slugify — inlined so the migration stays
    # runnable even if the service moves.
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:240].rstrip("-") or "session"


def upgrade() -> None:
    op.add_column("sessions", sa.Column("slug", sa.String(250), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, title FROM sessions ORDER BY created_at, id")
    ).all()
    taken: set[str] = set()
    for row in rows:
        base = _slugify(row.title)
        slug, n = base, 2
        while slug in taken:
            slug = f"{base}-{n}"
            n += 1
        taken.add(slug)
        bind.execute(
            sa.text("UPDATE sessions SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": row.id},
        )

    op.alter_column("sessions", "slug", nullable=False)
    op.create_index("ix_sessions_slug", "sessions", ["slug"], unique=True)

    op.add_column("session_feedback", sa.Column("structured", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("session_feedback", "structured")
    op.drop_index("ix_sessions_slug", table_name="sessions")
    op.drop_column("sessions", "slug")

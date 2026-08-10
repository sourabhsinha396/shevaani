"""drop CEFR levels

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10

Removes the CEFR band from sessions and the self-reported level from learners,
and drops the ``cefr_level`` type with them.

Matching people to an A2–C1 room is a real idea, but it needs enough sessions
running that a learner filtered to their band still finds one to book. Until
that is true the band mostly narrows an already short list, and a level nobody
acts on is worse than no level: it is a claim on the marketing pages that the
product does not deliver.

**The downgrade brings the columns back but not the data.** Dropping a column
throws its values away and Postgres keeps no copy, so ``users.level`` comes back
NULL and the session bands come back at the old A2/C1 defaults. Anyone who needs
the old values back needs a restore, not this. Said plainly here rather than
discovered later.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

cefr_level = postgresql.ENUM(
    "A1", "A2", "B1", "B2", "C1", "C2", name="cefr_level", create_type=False
)


def upgrade() -> None:
    op.drop_column("sessions", "level_min")
    op.drop_column("sessions", "level_max")
    op.drop_column("users", "level")
    # Only droppable once nothing references it, which is why it is last.
    cefr_level.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    cefr_level.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("level", cefr_level, nullable=True))
    op.add_column(
        "sessions",
        sa.Column("level_max", cefr_level, nullable=False, server_default="C1"),
    )
    op.add_column(
        "sessions",
        sa.Column("level_min", cefr_level, nullable=False, server_default="A2"),
    )

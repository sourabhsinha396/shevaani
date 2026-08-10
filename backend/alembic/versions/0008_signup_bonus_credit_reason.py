"""signup bonus credit reason

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-10

Adds ``signup_bonus`` to the ``credit_reason`` enum, so the welcome credit is
distinguishable from a support grant on the ledger. Both are +1 with a note;
only the reason says which one somebody is looking at, and "how many of these
did we hand out" is a question worth being able to answer with a WHERE clause.

``ALTER TYPE ... ADD VALUE`` is transactional on PostgreSQL 12+ **provided the
new value is not used in the same transaction**. Nothing here writes a row, so
this runs inside Alembic's transaction normally.

**The downgrade does not remove the value.** PostgreSQL has no
``ALTER TYPE ... DROP VALUE``; taking it out means recreating the type and
rewriting every column that uses it, which would rewrite the credit ledger —
the one table in this schema that is meant to be append-only and never
retroactively edited. A spare enum label costs nothing, so the downgrade is a
deliberate no-op rather than a destructive rebuild.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE credit_reason ADD VALUE IF NOT EXISTS 'signup_bonus'")


def downgrade() -> None:
    # Intentionally empty — see the module docstring.
    pass

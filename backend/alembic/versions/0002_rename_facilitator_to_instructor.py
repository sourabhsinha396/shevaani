"""rename facilitator to instructor

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08

A pure rename — no column is added, dropped or retyped, and no row is
rewritten. Every statement here is a catalogue update, so this is fast on any
table size.

Two things are worth knowing before reading it:

* ``ALTER TYPE ... RENAME VALUE`` needs Postgres 10+ and, unlike ``ADD VALUE``,
  is transactional. Existing ``users.role`` rows holding the old label pick up
  the new one automatically — the value's OID doesn't change.
* Renaming a table does *not* rename its indexes or constraints. Postgres is
  happy to leave ``ix_facilitator_blocks_facilitator_id`` sitting on
  ``instructor_blocks`` forever, but Alembic's autogenerate compares against the
  names our naming convention would produce, so leaving them stale would make
  every future autogenerate try to "fix" them. They are renamed explicitly.

The exclusion constraints from 0001 reference the renamed column, but Postgres
rewrites those references itself; only the constraint *names* need touching.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: (old, new) for everything that carries the word. Indexes and constraints are
#: split out because they need different DDL.
INDEXES = [
    ("ix_sessions_facilitator_id", "ix_sessions_instructor_id"),
    ("ix_facilitator_blocks_facilitator_id", "ix_instructor_blocks_instructor_id"),
]

TABLE_CONSTRAINTS = [
    ("sessions", "fk_sessions_facilitator_id_users", "fk_sessions_instructor_id_users"),
    (
        "sessions",
        "ex_sessions_facilitator_no_overlap",
        "ex_sessions_instructor_no_overlap",
    ),
    (
        "instructor_blocks",
        "pk_facilitator_blocks",
        "pk_instructor_blocks",
    ),
    (
        "instructor_blocks",
        "fk_facilitator_blocks_facilitator_id_users",
        "fk_instructor_blocks_instructor_id_users",
    ),
    (
        "instructor_blocks",
        "fk_facilitator_blocks_created_by_id_users",
        "fk_instructor_blocks_created_by_id_users",
    ),
    (
        "instructor_blocks",
        "ck_facilitator_blocks_ends_after_starts",
        "ck_instructor_blocks_ends_after_starts",
    ),
    (
        "instructor_blocks",
        "ex_facilitator_blocks_no_overlap",
        "ex_instructor_blocks_no_overlap",
    ),
]


def upgrade() -> None:
    # The enum label first: it is what the application's UserRole compares
    # against, and every other statement here is independent of it.
    op.execute("ALTER TYPE user_role RENAME VALUE 'facilitator' TO 'instructor'")

    # Table, then columns. The constraint renames below name the *new* table.
    op.execute("ALTER TABLE facilitator_blocks RENAME TO instructor_blocks")
    op.execute("ALTER TABLE sessions RENAME COLUMN facilitator_id TO instructor_id")
    op.execute("ALTER TABLE instructor_blocks RENAME COLUMN facilitator_id TO instructor_id")

    for old, new in INDEXES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")

    for table, old, new in TABLE_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")


def downgrade() -> None:
    for table, old, new in TABLE_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")

    for old, new in INDEXES:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")

    op.execute("ALTER TABLE instructor_blocks RENAME COLUMN instructor_id TO facilitator_id")
    op.execute("ALTER TABLE sessions RENAME COLUMN instructor_id TO facilitator_id")
    op.execute("ALTER TABLE instructor_blocks RENAME TO facilitator_blocks")

    op.execute("ALTER TYPE user_role RENAME VALUE 'instructor' TO 'facilitator'")

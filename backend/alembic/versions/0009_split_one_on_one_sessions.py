"""split one-to-one sessions into their own table

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-10

A one-to-one stops being "a session with min_seats = max_seats = 1" and becomes
its own table. Most of `sessions` was dead weight on a 1:1 — topic, level range,
prep material, seat counts — and the two have different lifecycles: a group
discussion is a catalogue row an admin publishes, a 1:1 is created by the
learner at the moment of booking and never exists unbooked.

The hard part is not the table. It is `ex_sessions_instructor_no_overlap` from
0001 — "a facilitator is never in two sessions at once, **of any kind**" — which
is a single-table exclusion constraint and therefore stops meaning anything the
moment half the sessions live somewhere else. Dropping to an application check
would undo the thing the comment in 0001 is proudest of, so instead:

    instructor_engagements

is a narrow table holding one row per live commitment — (instructor, range,
where it came from) — maintained by triggers on *both* session tables, carrying
the exclusion constraint. Two tables, one calendar, still enforced by Postgres
rather than by hope. It also generalises: anything else that occupies an
instructor's hour later (a cohort, a programme session) inserts here too and is
covered for free.

What is deliberately NOT duplicated:

- **The learner.** `bookings` remains the one record of who is attending what,
  because `ex_bookings_learner_no_overlap` is what stops a learner being in two
  places at once and it only works if every attendance is a booking row. So a
  1:1 has a booking, exactly as before; the booking just points at a different
  table.
- **The 1:1-vs-group buffer.** As in 0001, an exclusion constraint filters which
  *rows* participate, not which pairs, so the buffer can still only be expressed
  1:1-vs-1:1 (now a plain constraint on the new table rather than a partial one
  on `kind`). The 1:1-vs-group case stays in `services/scheduling.py` under an
  instructor row lock. Unchanged, neither better nor worse than before.

`sessions.kind` goes away with the rows it distinguished. The API still reports
`kind: "group"` so nothing downstream has to change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match ONE_ON_ONE_BUFFER_MINUTES in 0001 — same reasoning, same caveat:
# this is a database-level backstop and cannot read the runtime setting.
ONE_ON_ONE_BUFFER_MINUTES = 60


def upgrade() -> None:
    # ------------------------------------------------------------------ 1:1 table
    op.create_table(
        "one_on_one_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="session_status", create_type=False),
            nullable=False,
            server_default="published",
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_credits", sa.Integer(), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        sa.CheckConstraint("price_credits >= 0", name="price_non_negative"),
        # A 1:1 is created published, at the moment of booking. There is no
        # draft state to be in — nobody curates these.
        sa.CheckConstraint("status <> 'draft'", name="never_draft"),
        sa.ForeignKeyConstraint(
            ["instructor_id"],
            ["users.id"],
            name="fk_one_on_one_sessions_instructor_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_one_on_one_sessions_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_one_on_one_sessions"),
    )
    op.create_index(
        "ix_one_on_one_sessions_instructor_id", "one_on_one_sessions", ["instructor_id"]
    )
    op.create_index("ix_one_on_one_sessions_starts_at", "one_on_one_sessions", ["starts_at"])

    # ------------------------------------------------- the shared instructor calendar
    op.create_table(
        "instructor_engagements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        #: Which table the row mirrors. Not an enum: adding a third kind of
        #: commitment should not need a migration on a type.
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        sa.ForeignKeyConstraint(
            ["instructor_id"],
            ["users.id"],
            name="fk_instructor_engagements_instructor_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instructor_engagements"),
        sa.UniqueConstraint("source", "source_id", name="uq_instructor_engagements_source"),
    )

    # The whole point of the table.
    op.execute(
        """
        ALTER TABLE instructor_engagements
        ADD CONSTRAINT ex_instructor_engagements_no_overlap
        EXCLUDE USING gist (
            instructor_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        """
    )

    # ------------------------------------------------------- polymorphic children
    #
    # `session_id` becomes nullable and gains a sibling. Exactly one is set,
    # which `num_nonnulls` states in one line and the database then guarantees.
    op.add_column(
        "bookings",
        sa.Column("one_on_one_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.alter_column("bookings", "session_id", nullable=True)
    op.create_foreign_key(
        "fk_bookings_one_on_one_id_one_on_one_sessions",
        "bookings",
        "one_on_one_sessions",
        ["one_on_one_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_bookings_one_on_one_id", "bookings", ["one_on_one_id"])
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT ck_bookings_exactly_one_parent
        CHECK (num_nonnulls(session_id, one_on_one_id) = 1)
        """
    )
    # The 1:1 half of `uq_bookings_session_learner_active`. NULLs never collide
    # in a unique index, so without this the old index silently stops covering
    # anything whose parent is a 1:1.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_bookings_one_on_one_learner_active
        ON bookings (one_on_one_id, learner_id)
        WHERE status <> 'cancelled'
        """
    )

    op.add_column(
        "session_meetings",
        sa.Column("one_on_one_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # `session_id` was the primary key. It cannot be both nullable and the PK,
    # so the table gains a surrogate id and keeps one-meeting-per-parent as a
    # pair of partial unique indexes instead.
    op.execute("ALTER TABLE session_meetings DROP CONSTRAINT pk_session_meetings")
    op.add_column(
        "session_meetings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_primary_key("pk_session_meetings", "session_meetings", ["id"])
    op.alter_column("session_meetings", "session_id", nullable=True)
    op.create_foreign_key(
        "fk_session_meetings_one_on_one_id_one_on_one_sessions",
        "session_meetings",
        "one_on_one_sessions",
        ["one_on_one_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        ALTER TABLE session_meetings ADD CONSTRAINT ck_session_meetings_exactly_one_parent
        CHECK (num_nonnulls(session_id, one_on_one_id) = 1)
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_session_meetings_session ON session_meetings (session_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_session_meetings_one_on_one ON session_meetings (one_on_one_id)"
    )

    op.add_column(
        "join_access_logs",
        sa.Column("one_on_one_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.alter_column("join_access_logs", "session_id", nullable=True)
    op.create_foreign_key(
        "fk_join_access_logs_one_on_one_id_one_on_one_sessions",
        "join_access_logs",
        "one_on_one_sessions",
        ["one_on_one_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        ALTER TABLE join_access_logs ADD CONSTRAINT ck_join_access_logs_exactly_one_parent
        CHECK (num_nonnulls(session_id, one_on_one_id) = 1)
        """
    )

    # ------------------------------------------------------------- move the rows
    #
    # Ids are carried over rather than regenerated, so every child row can be
    # repointed by id alone and any id already in the wild — an email link, a
    # log line — still resolves.
    op.execute(
        """
        INSERT INTO one_on_one_sessions (
            id, status, title, starts_at, ends_at, price_credits,
            instructor_id, created_by_id, cancelled_at, cancellation_reason,
            created_at, updated_at
        )
        SELECT
            id, status, title, starts_at, ends_at, price_credits,
            instructor_id, created_by_id, cancelled_at, cancellation_reason,
            created_at, updated_at
        FROM sessions
        WHERE kind = 'one_on_one'
        """
    )
    # Order matters: point the children at the new parent before the old parent
    # is deleted, or ON DELETE CASCADE takes the bookings with it.
    for table in ("bookings", "session_meetings", "join_access_logs"):
        op.execute(
            f"""
            UPDATE {table} AS t
            SET one_on_one_id = t.session_id, session_id = NULL
            FROM sessions AS s
            WHERE s.id = t.session_id AND s.kind = 'one_on_one'
            """
        )
    op.execute("DELETE FROM sessions WHERE kind = 'one_on_one'")

    # -------------------------------------------------- retire the kind machinery
    op.execute(
        "ALTER TABLE sessions DROP CONSTRAINT IF EXISTS ex_sessions_one_on_one_buffer"
    )
    op.execute(
        "ALTER TABLE sessions DROP CONSTRAINT IF EXISTS "
        "ck_sessions_ck_sessions_one_on_one_is_single_seat"
    )
    op.drop_column("sessions", "kind")

    # The buffer, now a plain constraint on a table where every row is a 1:1.
    op.execute(
        f"""
        ALTER TABLE one_on_one_sessions ADD CONSTRAINT ex_one_on_one_buffer
        EXCLUDE USING gist (
            instructor_id WITH =,
            shevaani_buffered_range(starts_at, ends_at, {ONE_ON_ONE_BUFFER_MINUTES}) WITH &&
        ) WHERE (status <> 'cancelled')
        """
    )

    # --------------------------------------------------- triggers, then backfill
    #
    # Order is load-bearing. Created *after* the rows moved, so the INSERT above
    # does not fire them — otherwise the 1:1 engagements would be written twice,
    # once by the trigger and once by the backfill below, and the second would
    # collide on `uq_instructor_engagements_source`. Triggers last also means
    # the backfill is the single place existing rows are seeded from, for both
    # sources symmetrically, rather than one being an accident of ordering.
    #
    # Rows here are mirrored, never authored. `status` is read from the source:
    # a cancelled session frees the hour, which is what the `WHERE status <>
    # 'cancelled'` predicate did on the constraint this replaces.
    op.execute(
        """
        CREATE FUNCTION shevaani_sync_engagement() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                DELETE FROM instructor_engagements
                WHERE source = TG_ARGV[0] AND source_id = OLD.id;
                RETURN OLD;
            END IF;

            IF NEW.status = 'cancelled' THEN
                DELETE FROM instructor_engagements
                WHERE source = TG_ARGV[0] AND source_id = NEW.id;
                RETURN NEW;
            END IF;

            INSERT INTO instructor_engagements
                (instructor_id, starts_at, ends_at, source, source_id)
            VALUES (NEW.instructor_id, NEW.starts_at, NEW.ends_at, TG_ARGV[0], NEW.id)
            ON CONFLICT (source, source_id) DO UPDATE SET
                instructor_id = EXCLUDED.instructor_id,
                starts_at     = EXCLUDED.starts_at,
                ends_at       = EXCLUDED.ends_at;
            RETURN NEW;
        END;
        $$
        """
    )

    for table, source in (("sessions", "group"), ("one_on_one_sessions", "one_on_one")):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_sync_engagement
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION shevaani_sync_engagement('{source}')
            """
        )

    # If anything already live overlaps, the exclusion constraint says so here —
    # at deploy, where it can be looked at — rather than at the next booking.
    for table, source in (("sessions", "group"), ("one_on_one_sessions", "one_on_one")):
        op.execute(
            f"""
            INSERT INTO instructor_engagements
                (instructor_id, starts_at, ends_at, source, source_id)
            SELECT instructor_id, starts_at, ends_at, '{source}', id
            FROM {table} WHERE status <> 'cancelled'
            """
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sessions_sync_engagement ON sessions")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_one_on_one_sessions_sync_engagement ON one_on_one_sessions"
    )
    op.execute("DROP FUNCTION IF EXISTS shevaani_sync_engagement()")

    op.add_column(
        "sessions",
        sa.Column(
            "kind",
            postgresql.ENUM(name="session_kind", create_type=False),
            nullable=False,
            server_default="group",
        ),
    )

    # Back into `sessions`, filling in the columns a 1:1 never had.
    op.execute(
        """
        INSERT INTO sessions (
            id, kind, status, title, starts_at, ends_at,
            min_seats, max_seats, price_credits, level_min, level_max,
            instructor_id, created_by_id, cancelled_at, cancellation_reason,
            created_at, updated_at
        )
        SELECT
            id, 'one_on_one', status, title, starts_at, ends_at,
            1, 1, price_credits, 'A2', 'C1',
            instructor_id, created_by_id, cancelled_at, cancellation_reason,
            created_at, updated_at
        FROM one_on_one_sessions
        """
    )
    for table in ("bookings", "session_meetings", "join_access_logs"):
        op.execute(
            f"UPDATE {table} SET session_id = one_on_one_id, one_on_one_id = NULL "
            "WHERE one_on_one_id IS NOT NULL"
        )

    op.execute("ALTER TABLE sessions ALTER COLUMN kind DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE sessions ADD CONSTRAINT ck_sessions_ck_sessions_one_on_one_is_single_seat
        CHECK (kind <> 'one_on_one' OR (min_seats = 1 AND max_seats = 1))
        """
    )
    op.execute(
        f"""
        ALTER TABLE sessions ADD CONSTRAINT ex_sessions_one_on_one_buffer
        EXCLUDE USING gist (
            instructor_id WITH =,
            shevaani_buffered_range(starts_at, ends_at, {ONE_ON_ONE_BUFFER_MINUTES}) WITH &&
        ) WHERE (status <> 'cancelled' AND kind = 'one_on_one')
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_join_access_logs_one_on_one")
    op.execute(
        "ALTER TABLE join_access_logs DROP CONSTRAINT IF EXISTS "
        "ck_join_access_logs_exactly_one_parent"
    )
    op.drop_constraint(
        "fk_join_access_logs_one_on_one_id_one_on_one_sessions",
        "join_access_logs",
        type_="foreignkey",
    )
    op.drop_column("join_access_logs", "one_on_one_id")
    op.alter_column("join_access_logs", "session_id", nullable=False)

    op.execute("DROP INDEX IF EXISTS uq_session_meetings_one_on_one")
    op.execute("DROP INDEX IF EXISTS uq_session_meetings_session")
    op.execute(
        "ALTER TABLE session_meetings DROP CONSTRAINT IF EXISTS "
        "ck_session_meetings_exactly_one_parent"
    )
    op.drop_constraint(
        "fk_session_meetings_one_on_one_id_one_on_one_sessions",
        "session_meetings",
        type_="foreignkey",
    )
    op.drop_column("session_meetings", "one_on_one_id")
    op.execute("ALTER TABLE session_meetings DROP CONSTRAINT pk_session_meetings")
    op.drop_column("session_meetings", "id")
    op.alter_column("session_meetings", "session_id", nullable=False)
    op.create_primary_key("pk_session_meetings", "session_meetings", ["session_id"])

    op.execute("DROP INDEX IF EXISTS uq_bookings_one_on_one_learner_active")
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ck_bookings_exactly_one_parent")
    op.drop_index("ix_bookings_one_on_one_id", table_name="bookings")
    op.drop_constraint(
        "fk_bookings_one_on_one_id_one_on_one_sessions", "bookings", type_="foreignkey"
    )
    op.drop_column("bookings", "one_on_one_id")
    op.alter_column("bookings", "session_id", nullable=False)

    op.drop_table("instructor_engagements")
    op.drop_table("one_on_one_sessions")

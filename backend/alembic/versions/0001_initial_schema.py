"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-04

The interesting part of this migration is at the bottom: the exclusion
constraints that make double-booking physically impossible rather than merely
unlikely. Alembic cannot autogenerate those, so they are written by hand and
must be maintained by hand.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The buffer baked into the one-to-one exclusion constraint below. This is a
# database-level backstop, so it cannot read ONE_ON_ONE_BUFFER_MINUTES at
# runtime — if you change that setting, write a migration to match it.
ONE_ON_ONE_BUFFER_MINUTES = 60


user_role = postgresql.ENUM(
    "learner", "facilitator", "superuser", name="user_role", create_type=False
)
cefr_level = postgresql.ENUM(
    "A1", "A2", "B1", "B2", "C1", "C2", name="cefr_level", create_type=False
)
session_kind = postgresql.ENUM("group", "one_on_one", name="session_kind", create_type=False)
session_status = postgresql.ENUM(
    "draft", "published", "cancelled", "completed", name="session_status", create_type=False
)
booking_status = postgresql.ENUM(
    "pending",
    "confirmed",
    "waitlisted",
    "cancelled",
    "attended",
    "no_show",
    name="booking_status",
    create_type=False,
)
meeting_status = postgresql.ENUM(
    "pending", "ready", "failed", name="meeting_status", create_type=False
)
block_reason = postgresql.ENUM(
    "busy", "holiday", "sick", "other", name="block_reason", create_type=False
)
payment_provider = postgresql.ENUM(
    "stripe", "razorpay", name="payment_provider", create_type=False
)
payment_status = postgresql.ENUM(
    "created", "paid", "failed", "refunded", name="payment_status", create_type=False
)
credit_reason = postgresql.ENUM(
    "purchase",
    "booking_spend",
    "booking_refund",
    "session_cancelled",
    "admin_grant",
    "admin_revoke",
    name="credit_reason",
    create_type=False,
)

ALL_ENUMS = [
    user_role,
    cefr_level,
    session_kind,
    session_status,
    booking_status,
    meeting_status,
    block_reason,
    payment_provider,
    payment_status,
    credit_reason,
]

#: Booking statuses that hold a seat and therefore participate in overlap checks.
#: Waitlisted deliberately does not — being on two waitlists is fine.
ACTIVE_BOOKING_SQL = "'pending', 'confirmed', 'attended', 'no_show'"


def upgrade() -> None:
    bind = op.get_bind()

    # uuid = / timestamptz && in the same GiST index needs btree_gist.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    # ---------------------------------------------------------------- users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("level", cefr_level, nullable=True),
        sa.Column("billing_country", sa.String(2), nullable=True),
        sa.Column("preferred_provider", payment_provider, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("headline", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        # The unique constraint's backing index is the email lookup index — a
        # second plain index on the same column would only cost writes.
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "google_credentials",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("google_email", sa.String(320), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_google_credentials_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_google_credentials"),
    )

    # ------------------------------------------------------ facilitator blocks
    op.create_table(
        "facilitator_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("facilitator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", block_reason, nullable=False, server_default="busy"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("ends_at > starts_at", name="ck_facilitator_blocks_ends_after_starts"),
        sa.ForeignKeyConstraint(
            ["facilitator_id"],
            ["users.id"],
            name="fk_facilitator_blocks_facilitator_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_facilitator_blocks_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_facilitator_blocks"),
    )
    op.create_index("ix_facilitator_blocks_facilitator_id", "facilitator_blocks", ["facilitator_id"])

    # ------------------------------------------------------------- sessions
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("kind", session_kind, nullable=False),
        sa.Column("status", session_status, nullable=False, server_default="draft"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("topic", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prep_material_url", sa.Text(), nullable=True),
        sa.Column("level_min", cefr_level, nullable=False, server_default="A2"),
        sa.Column("level_max", cefr_level, nullable=False, server_default="C1"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("min_seats", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_seats", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("price_credits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("facilitator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("ends_at > starts_at", name="ck_sessions_ends_after_starts"),
        sa.CheckConstraint("min_seats >= 1", name="ck_sessions_min_seats_positive"),
        sa.CheckConstraint("max_seats >= min_seats", name="ck_sessions_max_seats_gte_min"),
        sa.CheckConstraint("price_credits >= 0", name="ck_sessions_price_non_negative"),
        sa.CheckConstraint(
            "kind <> 'one_on_one' OR (min_seats = 1 AND max_seats = 1)",
            name="ck_sessions_one_on_one_is_single_seat",
        ),
        sa.ForeignKeyConstraint(
            ["facilitator_id"], ["users.id"], name="fk_sessions_facilitator_id_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_sessions_created_by_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
    )
    op.create_index("ix_sessions_starts_at", "sessions", ["starts_at"])
    op.create_index("ix_sessions_facilitator_id", "sessions", ["facilitator_id"])
    # Catalogue query: published group sessions in the future, soonest first.
    op.create_index(
        "ix_sessions_catalogue",
        "sessions",
        ["kind", "status", "starts_at"],
    )

    op.create_table(
        "session_meetings",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="google_calendar"),
        sa.Column("status", meeting_status, nullable=False, server_default="pending"),
        sa.Column("calendar_event_id", sa.String(1024), nullable=True),
        sa.Column("host_google_email", sa.String(320), nullable=True),
        sa.Column("join_url", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name="fk_session_meetings_session_id_sessions", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_session_meetings"),
    )

    # ------------------------------------------------------------- bookings
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", booking_status, nullable=False, server_default="pending"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credits_spent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waitlist_position", sa.Integer(), nullable=True),
        sa.Column("first_joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendance_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("ends_at > starts_at", name="ck_bookings_ends_after_starts"),
        sa.CheckConstraint("credits_spent >= 0", name="ck_bookings_credits_non_negative"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name="fk_bookings_session_id_sessions", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["users.id"], name="fk_bookings_learner_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bookings"),
    )
    op.create_index("ix_bookings_session_id", "bookings", ["session_id"])
    op.create_index("ix_bookings_learner_id", "bookings", ["learner_id"])
    # Drives the hold sweeper.
    op.execute(
        "CREATE INDEX ix_bookings_expiring_holds ON bookings (hold_expires_at) "
        "WHERE status = 'pending'"
    )

    op.create_table(
        "join_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("denial_reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name="fk_join_access_logs_booking_id_bookings", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name="fk_join_access_logs_session_id_sessions", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_join_access_logs_user_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_join_access_logs"),
    )
    op.create_index("ix_join_access_logs_booking_id", "join_access_logs", ["booking_id"])

    # -------------------------------------------------------------- billing
    op.create_table(
        "credit_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("credits > 0", name="ck_credit_packs_credits_positive"),
        sa.CheckConstraint("amount_minor > 0", name="ck_credit_packs_amount_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_credit_packs"),
        sa.UniqueConstraint("slug", "currency", name="uq_credit_packs_slug_currency"),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("provider_order_id", sa.String(255), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", payment_status, nullable=False, server_default="created"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_payments_user_id_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"], ["credit_packs.id"], name="fk_payments_pack_id_credit_packs", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint("provider", "provider_order_id", name="uq_payments_provider_order"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])

    op.create_table(
        "credit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", credit_reason, nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("delta <> 0", name="ck_credit_ledger_delta_non_zero"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_credit_ledger_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name="fk_credit_ledger_booking_id_bookings", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"], ["payments.id"], name="fk_credit_ledger_payment_id_payments", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_credit_ledger"),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_events"),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )

    # ------------------------------------------------- correctness constraints
    #
    # These are the reason this project uses Postgres. Application code can and
    # will race; these cannot.

    # A facilitator is never in two sessions at once, of any kind.
    op.execute(
        """
        ALTER TABLE sessions ADD CONSTRAINT ex_sessions_facilitator_no_overlap
        EXCLUDE USING gist (
            facilitator_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status <> 'cancelled')
        """
    )

    # `timestamptz + interval` is STABLE, not IMMUTABLE — Postgres refuses it in
    # an index or exclusion-constraint expression ("functions in index expression
    # must be marked IMMUTABLE"). It is stable only because month and day
    # intervals depend on the TimeZone setting; a minute-based interval is plain
    # arithmetic on the epoch value and genuinely timezone-independent. So we wrap
    # it in a function declared IMMUTABLE, which is sound for this use and only
    # this use — do not call it with days or months.
    op.execute(
        """
        CREATE FUNCTION shevaani_buffered_range(
            ts_start timestamptz, ts_end timestamptz, buffer_minutes integer
        ) RETURNS tstzrange
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
        AS $$
            SELECT tstzrange(
                ts_start - make_interval(mins => buffer_minutes),
                ts_end   + make_interval(mins => buffer_minutes),
                '[)'
            )
        $$
        """
    )

    # One-to-one sessions additionally keep a buffer either side. An exclusion
    # constraint filters which *rows* participate, not which pairs, so this can
    # only express the 1:1-vs-1:1 case. The 1:1-vs-group case is enforced in
    # services/scheduling.py under a facilitator row lock.
    op.execute(
        f"""
        ALTER TABLE sessions ADD CONSTRAINT ex_sessions_one_on_one_buffer
        EXCLUDE USING gist (
            facilitator_id WITH =,
            shevaani_buffered_range(starts_at, ends_at, {ONE_ON_ONE_BUFFER_MINUTES}) WITH &&
        ) WHERE (status <> 'cancelled' AND kind = 'one_on_one')
        """
    )

    # A facilitator's blocked-time ranges never overlap each other.
    op.execute(
        """
        ALTER TABLE facilitator_blocks ADD CONSTRAINT ex_facilitator_blocks_no_overlap
        EXCLUDE USING gist (
            facilitator_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        """
    )

    # A learner is never booked into two overlapping sessions. Waitlisted rows
    # are excluded — sitting on two waitlists that clash is fine, and the
    # promotion path re-checks.
    op.execute(
        f"""
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_learner_no_overlap
        EXCLUDE USING gist (
            learner_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status IN ({ACTIVE_BOOKING_SQL}))
        """
    )

    # A learner books a given session at most once.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_bookings_session_learner_active
        ON bookings (session_id, learner_id)
        WHERE status <> 'cancelled'
        """
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.execute("DROP INDEX IF EXISTS uq_bookings_session_learner_active")
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ex_bookings_learner_no_overlap")
    op.execute(
        "ALTER TABLE facilitator_blocks DROP CONSTRAINT IF EXISTS ex_facilitator_blocks_no_overlap"
    )
    op.execute("ALTER TABLE sessions DROP CONSTRAINT IF EXISTS ex_sessions_one_on_one_buffer")
    op.execute("ALTER TABLE sessions DROP CONSTRAINT IF EXISTS ex_sessions_facilitator_no_overlap")
    op.execute("DROP FUNCTION IF EXISTS shevaani_buffered_range(timestamptz, timestamptz, integer)")

    op.drop_table("webhook_events")
    op.drop_table("credit_ledger")
    op.drop_table("payments")
    op.drop_table("credit_packs")
    op.drop_table("join_access_logs")
    op.drop_table("bookings")
    op.drop_table("session_meetings")
    op.drop_table("sessions")
    op.drop_table("facilitator_blocks")
    op.drop_table("google_credentials")
    op.drop_table("users")

    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)

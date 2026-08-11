"""group discussion transcripts and feedback

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-11

The Fireflies pipeline: transcripts of group discussions, the speaker → user
mapping (with a learned alias table so the mapping gets less manual every
week), and the per-booking feedback reports drafted by the model and published
by a human.

Also adds ``notetaker_dispatched_at`` to ``session_meetings`` — the cron that
sends the bot into a live Meet needs somewhere idempotent to say it already
has.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False: the explicit .create() below owns type creation. Without
# it, create_table auto-emits a second CREATE TYPE in the same transaction and
# the migration collides with itself.
transcript_status = postgresql.ENUM(
    "received", "needs_review", "resolved", "failed",
    name="transcript_status",
    create_type=False,
)
feedback_status = postgresql.ENUM(
    "draft", "published", name="feedback_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    transcript_status.create(bind, checkfirst=True)
    feedback_status.create(bind, checkfirst=True)

    op.add_column(
        "session_meetings",
        sa.Column("notetaker_dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "session_transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_transcript_id", sa.String(128), nullable=False),
        sa.Column("status", transcript_status, nullable=False),
        sa.Column("duration_minutes", sa.Float(), nullable=True),
        sa.Column("sentences", postgresql.JSONB(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_session_transcripts"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_session_transcripts_session_id_sessions",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("session_id", name="uq_session_transcripts_session_id"),
        sa.UniqueConstraint(
            "provider_transcript_id", name="uq_session_transcripts_provider_transcript_id"
        ),
    )

    op.create_table(
        "transcript_speakers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transcript_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("speaker_label", sa.String(200), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("resolved_via", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transcript_speakers"),
        sa.ForeignKeyConstraint(
            ["transcript_id"],
            ["session_transcripts.id"],
            name="fk_transcript_speakers_transcript_id_session_transcripts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_transcript_speakers_user_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("transcript_id", "speaker_label", name="uq_transcript_speaker_label"),
    )
    op.create_index(
        "ix_transcript_speakers_transcript_id", "transcript_speakers", ["transcript_id"]
    )

    op.create_table(
        "meet_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meet_aliases"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_meet_aliases_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "display_name", name="uq_meet_alias_user_name"),
    )

    op.create_table(
        "session_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transcript_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", feedback_status, nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("report_md", sa.Text(), nullable=False),
        sa.Column("generated_by", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_session_feedback"),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name="fk_session_feedback_booking_id_bookings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transcript_id"],
            ["session_transcripts.id"],
            name="fk_session_feedback_transcript_id_session_transcripts",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("booking_id", name="uq_session_feedback_booking_id"),
        sa.CheckConstraint(
            "(status <> 'published') OR (published_at IS NOT NULL)",
            name="ck_session_feedback_published_has_timestamp",
        ),
    )
    op.create_index("ix_session_feedback_transcript_id", "session_feedback", ["transcript_id"])


def downgrade() -> None:
    op.drop_index("ix_session_feedback_transcript_id", table_name="session_feedback")
    op.drop_table("session_feedback")
    op.drop_table("meet_aliases")
    op.drop_index("ix_transcript_speakers_transcript_id", table_name="transcript_speakers")
    op.drop_table("transcript_speakers")
    op.drop_table("session_transcripts")
    op.drop_column("session_meetings", "notetaker_dispatched_at")

    bind = op.get_bind()
    feedback_status.drop(bind, checkfirst=True)
    transcript_status.drop(bind, checkfirst=True)

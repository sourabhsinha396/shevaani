"""Group-discussion transcripts and the feedback reports built from them.

The pipeline: Fireflies' bot sits in the Meet → its webhook announces the
transcript → a worker stores it here (``SessionTranscript``), matches each
diarized speaker to a roster user (``TranscriptSpeaker``, remembering aliases
in ``MeetAlias``) → the model drafts one report per booking
(``SessionFeedback``) → a human publishes it from sqladmin.

Speaker mapping is its own table rather than JSON on the transcript so that
fixing a mis-attributed "Harsh" in sqladmin is editing one row with a user
dropdown, not hand-editing a blob.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.booking import Booking
from app.models.enums import FeedbackStatus, TranscriptStatus
from app.models.session import Session
from app.models.types import pg_enum
from app.models.user import User


class SessionTranscript(Base, UUIDPrimaryKey, Timestamped):
    """One group discussion's diarized transcript, as fetched from Fireflies.

    ``sentences`` is the raw material for everything downstream:
    ``[{"speaker": str, "text": str, "start": float, "end": float}, ...]``,
    times in seconds from the start of the call. Stored verbatim so resolution
    and generation can be re-run without another API round trip — and so the
    transcript survives Fireflies' storage limits.
    """

    __tablename__ = "session_transcripts"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    #: Fireflies' id — what the webhook quotes and the dedupe key for redeliveries.
    provider_transcript_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    status: Mapped[TranscriptStatus] = mapped_column(
        pg_enum(TranscriptStatus, "transcript_status"),
        nullable=False,
        default=TranscriptStatus.RECEIVED,
    )

    duration_minutes: Mapped[float | None] = mapped_column(Float)
    sentences: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(Text)

    session: Mapped[Session] = relationship()
    speakers: Mapped[list[TranscriptSpeaker]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return f"Transcript ({self.status.value})"


class TranscriptSpeaker(Base, UUIDPrimaryKey, Timestamped):
    """One diarized speaker label and who it turned out to be.

    ``user_id`` NULL with ``ignored`` False is the "needs a human" state — in
    sqladmin that is a row whose user dropdown is empty. Set the user (or tick
    ``ignored`` for the bot / a stray guest) and re-run generation.
    """

    __tablename__ = "transcript_speakers"
    __table_args__ = (
        UniqueConstraint("transcript_id", "speaker_label", name="uq_transcript_speaker_label"),
    )

    transcript_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("session_transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: The display name exactly as it appears in the transcript.
    speaker_label: Mapped[str] = mapped_column(String(200), nullable=False)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    #: The bot itself, or someone who is not on the roster. Ignored speakers'
    #: lines stay in the transcript but produce no report.
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: 0–1 from the resolver; NULL when a human set the mapping.
    confidence: Mapped[float | None] = mapped_column(Float)
    #: "auto" or "admin" — whether to trust it for alias learning is the same
    #: question either way, so both feed ``meet_aliases``.
    resolved_via: Mapped[str | None] = mapped_column(String(16))

    transcript: Mapped[SessionTranscript] = relationship(back_populates="speakers")
    user: Mapped[User | None] = relationship()

    def __str__(self) -> str:
        return self.speaker_label


class MeetAlias(Base, UUIDPrimaryKey, Timestamped):
    """Display names a user has been seen joining under. The resolver's memory:
    once "harshu2004" has been mapped to Harsh, every later session with that
    label resolves without a human."""

    __tablename__ = "meet_aliases"
    __table_args__ = (
        UniqueConstraint("user_id", "display_name", name="uq_meet_alias_user_name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    #: Stored lowercased/stripped — the same normalisation the resolver matches on.
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship()

    def __str__(self) -> str:
        return self.display_name


class SessionFeedback(Base, UUIDPrimaryKey, Timestamped):
    """One learner's report for one group discussion.

    Keyed on the booking, not the user: the booking is what says they were in
    that room, and it makes "one report per seat" a constraint instead of a
    convention. Regeneration overwrites drafts in place; a published report is
    never overwritten by the pipeline — unpublish it first if it must change.
    """

    __tablename__ = "session_feedback"
    __table_args__ = (
        CheckConstraint(
            "(status <> 'published') OR (published_at IS NOT NULL)",
            name="published_has_timestamp",
        ),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("session_transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[FeedbackStatus] = mapped_column(
        pg_enum(FeedbackStatus, "feedback_status"),
        nullable=False,
        default=FeedbackStatus.DRAFT,
    )

    #: Deterministic numbers computed in code, not by the model: talk-time
    #: share, turns, longest monologue, questions asked, filler words, and the
    #: peer comparison used for the talk-time graph and rank. Shape documented
    #: in ``services/transcripts.py::speaker_metrics`` and
    #: ``services/feedback.py::generate_feedback``.
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    #: The model's answer as structured JSON (summary, strengths,
    #: areas_to_improve, language_notes, collaboration, suggestions) — the
    #: template the frontend renders section by section. NULL for silent
    #: participants and reports generated before this column existed.
    structured: Mapped[dict | None] = mapped_column(JSONB)
    #: The GD score: composite 0-100, five pillar scores, the deterministic
    #: subscores and LLM rubric integers behind them, plus ``rubric_version``
    #: and the scoring model — so trends can respect scoring-rule boundaries.
    #: Shape documented in ``services/gd_score.py::compute_gd_score``. NULL for
    #: silent participants and reports scored before this existed.
    score: Mapped[dict | None] = mapped_column(JSONB)
    #: The learner-facing report, markdown. Editable in sqladmin before publish.
    #: Rendered from ``structured`` in code; also what the report email sends.
    report_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Which model wrote the draft — so a bad batch is traceable to its author.
    generated_by: Mapped[str | None] = mapped_column(String(64))

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: When the report was last emailed to the learner. The email button's
    #: "already sent" signal, not a delivery receipt.
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking: Mapped[Booking] = relationship()
    transcript: Mapped[SessionTranscript] = relationship()

    def __str__(self) -> str:
        return f"Feedback ({self.status.value})"

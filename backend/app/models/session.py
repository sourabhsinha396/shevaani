from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import MeetingStatus, SessionStatus
from app.models.types import pg_enum
from app.models.user import User


class Session(Base, UUIDPrimaryKey, Timestamped):
    """A group discussion: a catalogue row an admin publishes and learners book
    seats on.

    One-to-ones used to live here too, as a session with min_seats = max_seats
    = 1. They are their own table now (see ``OneOnOneSession`` below and
    migration 0009) — everything on this class from ``topic`` down to
    ``max_seats`` was dead weight on one.

    There is no CEFR band on a session any more (migration 0011). Sorting people
    into A2–C1 rooms was a promise the product could not keep with the number of
    sessions it runs, and half-keeping it was worse than not making it.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("min_seats >= 1", name="min_seats_positive"),
        CheckConstraint("max_seats >= min_seats", name="max_seats_gte_min"),
        CheckConstraint("price_credits >= 0", name="price_non_negative"),
    )

    status: Mapped[SessionStatus] = mapped_column(
        pg_enum(SessionStatus, "session_status"), nullable=False, default=SessionStatus.DRAFT
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    #: Article link / question list emailed to learners before the session.
    prep_material_url: Mapped[str | None] = mapped_column(Text)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    min_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    #: Callable so the default is read at insert time rather than frozen at
    #: import — the setting is the one place the price lives.
    price_credits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=lambda: settings.session_price_credits
    )

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    instructor: Mapped[User] = relationship(foreign_keys=[instructor_id])
    meeting: Mapped[SessionMeeting | None] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
        primaryjoin="Session.id == SessionMeeting.session_id",
    )
    bookings: Mapped[list[Booking]] = relationship(  # noqa: F821
        back_populates="session",
        cascade="all, delete-orphan",
        primaryjoin="Session.id == Booking.session_id",
    )

    def __str__(self) -> str:
        return f"{self.title} — {self.starts_at:%d %b %Y %H:%M} UTC"

    @property
    def is_bookable(self) -> bool:
        return self.status == SessionStatus.PUBLISHED


class OneOnOneSession(Base, UUIDPrimaryKey, Timestamped):
    """One learner, one instructor, one hour.

    Created by the learner at the moment of booking and never exists unbooked,
    which is why there is no draft state and no seat count: the row *is* the
    commitment. Who it is for lives on the ``Booking``, not here — see the note
    in migration 0009. Duplicating the learner would give two answers to the
    same question and quietly take the row out from under
    ``ex_bookings_learner_no_overlap``, which is the only thing stopping
    somebody being in two places at once.

    Overlap with *any* other commitment, group or one-to-one, is enforced
    through ``instructor_engagements`` rather than a constraint on this table —
    an exclusion constraint cannot reach across tables.
    """

    __tablename__ = "one_on_one_sessions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("price_credits >= 0", name="price_non_negative"),
        CheckConstraint("status <> 'draft'", name="never_draft"),
        # `ex_one_on_one_buffer` also lives on this table. It is an exclusion
        # constraint, so it is written by hand in the migration.
    )

    status: Mapped[SessionStatus] = mapped_column(
        pg_enum(SessionStatus, "session_status"), nullable=False, default=SessionStatus.PUBLISHED
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    price_credits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=lambda: settings.session_price_credits
    )

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    #: The learner who booked it. Kept for provenance only — the booking is what
    #: says whether they turned up, cancelled, or were refunded.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    instructor: Mapped[User] = relationship(foreign_keys=[instructor_id])
    meeting: Mapped[SessionMeeting | None] = relationship(
        back_populates="one_on_one",
        uselist=False,
        cascade="all, delete-orphan",
        primaryjoin="OneOnOneSession.id == SessionMeeting.one_on_one_id",
    )
    bookings: Mapped[list[Booking]] = relationship(  # noqa: F821
        back_populates="one_on_one",
        cascade="all, delete-orphan",
        primaryjoin="OneOnOneSession.id == Booking.one_on_one_id",
    )

    def __str__(self) -> str:
        return f"{self.title} — {self.starts_at:%d %b %Y %H:%M} UTC"

    @property
    def is_bookable(self) -> bool:
        return self.status == SessionStatus.PUBLISHED

    @property
    def booking(self) -> Booking | None:  # noqa: F821
        """The one booking, if it is loaded. A 1:1 never has more than one."""
        return self.bookings[0] if self.bookings else None


class InstructorEngagement(Base):
    """One row per hour an instructor is committed, whatever committed them.

    **Read-only from Python.** Rows are written by database triggers on
    ``sessions`` and ``one_on_one_sessions`` (migration 0009); writing one by
    hand would put it out of step with the row it mirrors. It exists as a model
    so scheduling can ask "is this instructor free?" of one table instead of
    unioning every table that might have booked them.

    The exclusion constraint it carries is what makes double-booking across the
    two session tables impossible rather than merely unlikely.
    """

    __tablename__ = "instructor_engagements"

    #: Values of `source`. Not an enum type — adding a third kind of commitment
    #: should not need a migration, only a constant.
    GROUP = "group"
    ONE_ON_ONE = "one_on_one"

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        # One row per source row — what makes the triggers' upsert work.
        UniqueConstraint("source", "source_id", name="uq_instructor_engagements_source"),
        # `ex_instructor_engagements_no_overlap` is an exclusion constraint and
        # lives in the migration. It is the reason this table exists.
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: ``group`` or ``one_on_one`` — which table ``source_id`` points into.
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    def __str__(self) -> str:
        return f"{self.source} · {self.starts_at:%d %b %H:%M} UTC"


class SessionMeeting(Base, UUIDPrimaryKey, Timestamped):
    """The Google Calendar event + Meet link for a session of either kind.

    Kept in its own table on purpose: creating a session must not depend on
    Google being reachable. The worker fills this in and a failure here is
    visible and retryable without touching the session row.

    Exactly one of ``session_id`` / ``one_on_one_id`` is set — the database
    checks it. It used to be keyed on ``session_id`` alone; the surrogate key
    is what lets that column be null for a one-to-one's meeting.
    """

    __tablename__ = "session_meetings"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(session_id, one_on_one_id) = 1", name="exactly_one_parent"
        ),
        # One meeting per session, which the old `session_id` primary key used
        # to give for free. Nulls don't collide, so each covers only its own kind.
        Index("uq_session_meetings_session", "session_id", unique=True),
        Index("uq_session_meetings_one_on_one", "one_on_one_id", unique=True),
    )

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    one_on_one_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("one_on_one_sessions.id", ondelete="CASCADE")
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google_calendar")
    status: Mapped[MeetingStatus] = mapped_column(
        pg_enum(MeetingStatus, "meeting_status"), nullable=False, default=MeetingStatus.PENDING
    )

    calendar_event_id: Mapped[str | None] = mapped_column(String(1024))
    #: The account whose calendar holds the event — i.e. the Meet host.
    host_google_email: Mapped[str | None] = mapped_column(String(320))
    #: Bearer credential. Never serialise this outside GET /sessions/{id}/join.
    join_url: Mapped[str | None] = mapped_column(Text)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    session: Mapped[Session | None] = relationship(
        back_populates="meeting", foreign_keys=[session_id]
    )
    one_on_one: Mapped[OneOnOneSession | None] = relationship(
        back_populates="meeting", foreign_keys=[one_on_one_id]
    )

    def __str__(self) -> str:
        return f"Meet ({self.status.value})"

    @property
    def is_ready(self) -> bool:
        return self.status == MeetingStatus.READY and bool(self.join_url)

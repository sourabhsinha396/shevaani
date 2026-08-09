from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CEFRLevel, MeetingStatus, SessionKind, SessionStatus
from app.models.types import pg_enum
from app.models.user import User


class Session(Base, UUIDPrimaryKey, Timestamped):
    """One bookable event. Group discussions and one-to-ones share this table —
    a one-to-one is just a session with min_seats = max_seats = 1."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("min_seats >= 1", name="min_seats_positive"),
        CheckConstraint("max_seats >= min_seats", name="max_seats_gte_min"),
        CheckConstraint("price_credits >= 0", name="price_non_negative"),
        CheckConstraint(
            "kind <> 'one_on_one' OR (min_seats = 1 AND max_seats = 1)",
            name="one_on_one_is_single_seat",
        ),
    )

    kind: Mapped[SessionKind] = mapped_column(pg_enum(SessionKind, "session_kind"), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        pg_enum(SessionStatus, "session_status"), nullable=False, default=SessionStatus.DRAFT
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    #: Article link / question list emailed to learners before the session.
    prep_material_url: Mapped[str | None] = mapped_column(Text)

    level_min: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, "cefr_level"), nullable=False, default=CEFRLevel.A2
    )
    level_max: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, "cefr_level"), nullable=False, default=CEFRLevel.C1
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    min_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    price_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    bookings: Mapped[list[Booking]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return f"{self.title} — {self.starts_at:%d %b %Y %H:%M} UTC"

    @property
    def is_bookable(self) -> bool:
        return self.status == SessionStatus.PUBLISHED


class SessionMeeting(Base, Timestamped):
    """The Google Calendar event + Meet link for a session.

    Kept in its own table on purpose: creating a session must not depend on
    Google being reachable. The worker fills this in and a failure here is
    visible and retryable without touching the session row.
    """

    __tablename__ = "session_meetings"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
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

    session: Mapped[Session] = relationship(back_populates="meeting")

    def __str__(self) -> str:
        return f"Meet ({self.status.value})"

    @property
    def is_ready(self) -> bool:
        return self.status == MeetingStatus.READY and bool(self.join_url)

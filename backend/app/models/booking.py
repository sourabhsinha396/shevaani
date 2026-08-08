from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import BookingStatus
from app.models.session import Session
from app.models.types import pg_enum
from app.models.user import User


class Booking(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("credits_spent >= 0", name="credits_non_negative"),
        # Uniqueness per learner and the learner-overlap exclusion live in the
        # migration — both are partial and Alembic can't infer them.
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        pg_enum(BookingStatus, "booking_status"), nullable=False, default=BookingStatus.PENDING
    )

    # Denormalised from the session so a learner can't be in two places at once —
    # an exclusion constraint can't reach across tables.
    #
    # INVARIANT: rescheduling a session MUST update its bookings' starts_at/ends_at
    # in the same transaction. See services/session_admin.py::reschedule_session.
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    credits_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Set while status is PENDING; the sweeper releases the seat once it passes.
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: 1-based position among waitlisted bookings for the session.
    waitlist_position: Mapped[int | None] = mapped_column(Integer)

    #: First time the learner fetched the join link — the automatic attendance signal.
    first_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Set by the instructor afterwards; overrides the join-click signal.
    attendance_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    session: Mapped[Session] = relationship(back_populates="bookings")
    learner: Mapped[User] = relationship(foreign_keys=[learner_id])


class JoinAccessLog(Base, UUIDPrimaryKey):
    """Every hit on the gated join endpoint. The join URL is a bearer credential,
    so we keep an audit trail — it's also the raw material for attendance."""

    __tablename__ = "join_access_logs"

    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted: Mapped[bool] = mapped_column(nullable=False, default=False)
    denial_reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)

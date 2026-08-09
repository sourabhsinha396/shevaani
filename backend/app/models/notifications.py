from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKey


class SessionReminder(Base, UUIDPrimaryKey):
    """One row per (session, reminder). Its only job is to stop a second send.

    A reminder job could dedupe on a time window instead — "sessions starting in
    the next fifteen minutes" — but then a worker restart, a clock skew or an
    overlapping run mails everybody twice, and the failure is invisible until a
    learner complains. The unique constraint makes a double send a database
    error rather than an inbox event.

    It is also the answer to "did we actually remind them?", which is the first
    question asked after a no-show.
    """

    __tablename__ = "session_reminders"
    __table_args__ = (
        UniqueConstraint("session_id", "hours_before", name="uq_session_reminders_session_hours"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Which of the configured offsets this row represents (24, 1, …).
    hours_before: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: How many learners it went to. Zero is a legitimate outcome — everybody
    #: cancelled — and worth being able to tell apart from "never ran".
    recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

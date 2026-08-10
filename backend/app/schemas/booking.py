from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field

from app.models.enums import BookingStatus, MeetingStatus
from app.schemas.common import ORMModel
from app.schemas.session import SessionOut


class BookingOut(ORMModel):
    id: uuid.UUID
    #: Whatever was booked — a group discussion or a one-to-one. Read from
    #: ``Booking.parent_id`` because since 0009 only one of the two columns is
    #: ever set, and a client needs one id rather than a pair plus the rule for
    #: picking between them.
    session_id: uuid.UUID = Field(
        validation_alias=AliasChoices("parent_id", "session_id")
    )
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime
    credits_spent: int
    waitlist_position: int | None = None


class BookingWithSessionOut(BookingOut):
    session: SessionOut
    #: The Meet link for the learner's own booking, from the moment the worker
    #: has one. It used to be served only by ``GET /sessions/{id}/join``, and
    #: only inside the join window — but a Meet room admits nobody until the
    #: host arrives, so withholding it bought no safety and cost the learner the
    #: one thing they came to this page for. Null on a waitlisted booking, on a
    #: cancelled session, and while the meeting is still being created.
    join_url: str | None = None
    #: Why ``join_url`` is null, when it is — "still being made" and "we failed
    #: to make it" are different things to say to someone.
    meeting_status: MeetingStatus | None = None


class OneOnOneBookIn(BaseModel):
    #: Optional, and normally absent. The booking page pools availability across
    #: the team and never names anyone, so the server picks a free instructor at
    #: random. Kept on the schema for the admin and scripted paths that do mean
    #: a particular person.
    instructor_id: uuid.UUID | None = None
    starts_at: datetime
    duration_minutes: int | None = Field(default=None, ge=15, le=240)


class CancelBookingIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class CreditBalanceOut(BaseModel):
    balance: int


class LedgerEntryOut(ORMModel):
    id: uuid.UUID
    delta: int
    reason: str
    note: str | None
    created_at: datetime

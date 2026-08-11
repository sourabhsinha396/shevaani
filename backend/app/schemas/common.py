from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    timezone: str
    #: Null means unconfirmed. Advisory — nothing is blocked by it; the frontend
    #: uses it to offer a resend.
    email_verified_at: datetime | None = None
    #: Your own code, for building invite links (``?r=<code>``). Only ever the
    #: authenticated caller's — nothing serialises somebody else's through this.
    referral_code: str | None = None
    headline: str | None = None
    bio: str | None = None


class InstructorOut(ORMModel):
    id: uuid.UUID
    full_name: str
    headline: str | None = None
    bio: str | None = None


class Message(BaseModel):
    detail: str


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class SlotOut(BaseModel):
    starts_at: datetime
    ends_at: datetime


class DayAvailabilityOut(BaseModel):
    """One local calendar date and the slot starts open on it, in UTC.

    Only the start is sent: every slot on the response runs for the same
    ``duration_minutes`` that was asked for, so an end per slot would be the
    same arithmetic repeated a few hundred times.
    """

    date: date
    slots: list[datetime]


class AvailabilityOut(BaseModel):
    #: The zone the ``date`` keys are calendar dates *in* — the business's own,
    #: not the caller's. A learner in Sydney sees these instants rendered in
    #: whatever zone they picked, which can put them on a different date.
    timezone: str
    duration_minutes: int
    days: list[DayAvailabilityOut]


class AvailabilitySummaryOut(BaseModel):
    """Whether one-to-one is bookable at all, for the site chrome.

    Deliberately not a slot list: this is fetched on every page load to decide
    whether the nav offers 1:1 at all, so it answers one question and carries
    no calendar with it. ``next_slot`` is advisory — by the time anyone clicks,
    somebody else may have taken it.
    """

    has_slots: bool
    next_slot: datetime | None = None
    #: How far ahead the question was asked, so a caller can say "nothing in the
    #: next 31 days" rather than "never".
    horizon_days: int

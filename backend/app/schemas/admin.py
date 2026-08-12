from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BookingStatus, CreditReason
from app.schemas.common import ORMModel


class LearnerSummaryOut(BaseModel):
    id: uuid.UUID
    full_name: str
    #: Plain ``str`` on the way out. ``EmailStr`` here would 500 a whole listing
    #: over one legacy address the validator dislikes (`.local`, say).
    email: str
    is_active: bool
    timezone: str
    created_at: datetime
    balance: int
    upcoming_bookings: int


class LedgerEntryOut(ORMModel):
    id: uuid.UUID
    delta: int
    reason: CreditReason
    note: str | None = None
    booking_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    created_at: datetime


class LearnerBookingOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    session_title: str
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime
    credits_spent: int
    waitlist_position: int | None = None
    cancelled_at: datetime | None = None


class LearnerDetailOut(BaseModel):
    learner: LearnerSummaryOut
    bookings: list[LearnerBookingOut]
    ledger: list[LedgerEntryOut]


class CreditAdjustIn(BaseModel):
    """A signed adjustment, so one endpoint covers granting and revoking.

    The ledger is append-only: a revoke is a negative row, never an edit.
    """

    delta: int = Field(ge=-500, le=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("delta")
    @classmethod
    def _non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("delta must not be zero")
        return value


class CreditBalanceOut(BaseModel):
    balance: int


class CreditAdjustByEmailIn(CreditAdjustIn):
    """The same signed adjustment, addressed by email instead of id — for the
    credits screen, where support has an address and not a UUID."""

    email: str = Field(min_length=3, max_length=320)


class CreditAdjustByEmailOut(BaseModel):
    """Echoes who was credited, so the screen can confirm it hit the right
    account before the admin closes the tab."""

    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    balance: int


class InstructorAdminOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool
    headline: str | None = None
    bio: str | None = None
    google_connected: bool
    google_email: str | None = None
    upcoming_sessions: int = 0


class InstructorAdminIn(BaseModel):
    """Instructors are still created from the CLI (PLAN decision 10) — this only
    edits the ones that exist."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    headline: str | None = Field(default=None, max_length=200)
    bio: str | None = None
    is_active: bool | None = None


class CancellationImpactOut(BaseModel):
    bookings_affected: int
    learners_refunded: int
    credits_refunded: int
    waitlisted: int


class ContactHandledIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


# ------------------------------------------------------------- analytics


class AnalyticsDayOut(BaseModel):
    """One local calendar day (business timezone) of the headline series."""

    date: date
    signups: int
    bookings: int
    payments: int


class RevenueByCurrencyOut(BaseModel):
    """Settled money in one currency, minor units. Deliberately *not* summed
    across currencies — ₹ plus € is not a number, and pretending it is would
    put a wrong figure on the most-read screen in the admin."""

    currency: str
    amount_minor: int
    payments: int


class TopReferrerOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    joined: int
    enrolled: int
    credits_earned: int


class AnalyticsTotalsOut(BaseModel):
    #: All-time headcounts, not windowed — "how big are we" reads wrong scoped
    #: to a month.
    learners: int
    #: Everything below is scoped to the requested window.
    new_learners: int
    bookings_confirmed: int
    bookings_cancelled: int
    payments_paid: int
    credits_purchased: int
    credits_spent: int
    referrals_joined: int
    referrals_enrolled: int
    referral_credits_awarded: int


class AnalyticsOut(BaseModel):
    days: int
    totals: AnalyticsTotalsOut
    revenue: list[RevenueByCurrencyOut]
    series: list[AnalyticsDayOut]
    #: All-time, because a leaderboard that resets monthly with three users on
    #: it would mostly be empty.
    top_referrers: list[TopReferrerOut]

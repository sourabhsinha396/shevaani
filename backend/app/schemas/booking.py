from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import BookingStatus
from app.schemas.common import ORMModel
from app.schemas.session import SessionOut


class BookingOut(ORMModel):
    id: uuid.UUID
    session_id: uuid.UUID
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime
    credits_spent: int
    waitlist_position: int | None = None


class BookingWithSessionOut(BookingOut):
    session: SessionOut


class OneOnOneBookIn(BaseModel):
    instructor_id: uuid.UUID
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

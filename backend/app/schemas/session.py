from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    BlockReason,
    BookingStatus,
    CEFRLevel,
    MeetingStatus,
    SessionKind,
    SessionStatus,
)
from app.schemas.common import InstructorOut, ORMModel


class SessionOut(ORMModel):
    """Public catalogue shape.

    Deliberately has no join_url — that is a bearer credential and is only ever
    served by GET /sessions/{id}/join.
    """

    id: uuid.UUID
    #: Group or one-to-one. Serialised because a client cannot infer it — a
    #: group discussion with one seat left, and a 1:1, are not the same thing
    #: even though ``max_seats`` can be 1 for both.
    kind: SessionKind
    title: str
    topic: str | None
    description: str | None
    prep_material_url: str | None
    level_min: CEFRLevel
    level_max: CEFRLevel
    starts_at: datetime
    ends_at: datetime
    min_seats: int
    max_seats: int
    price_credits: int
    status: SessionStatus
    instructor: InstructorOut

    seats_taken: int = 0
    seats_left: int = 0
    is_full: bool = False
    my_booking_status: BookingStatus | None = None


class SessionAdminOut(SessionOut):
    """Adds the operational bits only superusers should see."""

    meeting_status: MeetingStatus | None = None
    meeting_last_error: str | None = None
    meeting_host_email: str | None = None
    waitlist_count: int = 0


class GroupSessionCreateIn(BaseModel):
    instructor_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=200)
    description: str | None = None
    prep_material_url: str | None = None
    starts_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=240)
    min_seats: int = Field(default=3, ge=1, le=50)
    max_seats: int = Field(default=6, ge=1, le=50)
    price_credits: int = Field(default=1, ge=0, le=100)
    level_min: CEFRLevel = CEFRLevel.A2
    level_max: CEFRLevel = CEFRLevel.C1
    publish: bool = False

    @model_validator(mode="after")
    def _check(self) -> GroupSessionCreateIn:
        if self.max_seats < self.min_seats:
            raise ValueError("max_seats must be at least min_seats")
        if self.starts_at.tzinfo is None:
            raise ValueError("starts_at must include a timezone offset")
        return self


class GroupSessionUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=200)
    description: str | None = None
    prep_material_url: str | None = None
    min_seats: int | None = Field(default=None, ge=1, le=50)
    max_seats: int | None = Field(default=None, ge=1, le=50)
    price_credits: int | None = Field(default=None, ge=0, le=100)
    level_min: CEFRLevel | None = None
    level_max: CEFRLevel | None = None


class RescheduleIn(BaseModel):
    starts_at: datetime
    duration_minutes: int | None = Field(default=None, ge=15, le=240)


class CancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class JoinOut(BaseModel):
    join_url: str
    session_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime


class BlockIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: BlockReason = BlockReason.BUSY
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check(self) -> BlockIn:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("timestamps must include a timezone offset")
        return self


class BlockOut(ORMModel):
    id: uuid.UUID
    instructor_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    reason: BlockReason
    note: str | None

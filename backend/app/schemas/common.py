from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import CEFRLevel, UserRole


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
    level: CEFRLevel | None = None
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

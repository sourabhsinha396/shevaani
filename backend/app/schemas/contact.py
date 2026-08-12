from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=10, max_length=5000)
    #: From the v2 checkbox; whether one is required is the route's decision,
    #: made against ``settings.recaptcha_configured``. See schemas/auth.py.
    recaptcha_token: str | None = Field(default=None, max_length=4096)


class ContactMessageOut(ORMModel):
    id: uuid.UUID
    name: str
    #: Plain ``str``, not ``EmailStr``: this validates on the way *out*, and an
    #: address already in the database failing validation would turn a listing
    #: into a 500 rather than telling anyone anything useful.
    email: str
    subject: str
    body: str
    user_id: uuid.UUID | None = None
    created_at: datetime
    handled_at: datetime | None = None
    handled_note: str | None = None

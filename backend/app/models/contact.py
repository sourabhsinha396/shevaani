from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey
from app.models.user import User


class ContactMessage(Base, UUIDPrimaryKey):
    """A message from the public contact form.

    Stored rather than emailed: a table survives a mail provider outage, and a payment provider
    reviewing the account needs the contact route to actually work today. The
    row is the record; an email notification can be layered on later without
    changing the endpoint.
    """

    __tablename__ = "contact_messages"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    #: Set when the sender was signed in. Anonymous submissions are allowed.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Free-text note from whoever dealt with it.
    handled_note: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship()

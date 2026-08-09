from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CEFRLevel, PaymentProvider, UserRole
from app.models.types import pg_enum


class User(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.LEARNER
    )

    #: IANA name, e.g. "Asia/Kolkata". Everything is stored UTC and rendered in this.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    level: Mapped[CEFRLevel | None] = mapped_column(pg_enum(CEFRLevel, "cefr_level"))

    #: ISO-3166 alpha-2, captured at signup. Decides Razorpay vs Stripe and stays
    #: stable across purchases so a learner's checkout never changes under them.
    billing_country: Mapped[str | None] = mapped_column(String(2))
    preferred_provider: Mapped[PaymentProvider | None] = mapped_column(
        pg_enum(PaymentProvider, "payment_provider")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    #: When the learner proved they can read this address. Advisory: nothing is
    #: blocked while it is NULL — it decides whether we trust the address enough
    #: to send reminders to it, and whether the dashboard nags.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Set on every password change. Access and refresh tokens issued before this
    #: are refused, which is what makes a reset log the other browsers out —
    #: the tokens are stateless JWTs and there is nothing else to revoke.
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Instructor-only
    bio: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(200))

    google_credential: Mapped[GoogleCredential | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        # What the data-plane admin prints for a related row. Without it the
        # link text is `<app.models.user.User object at 0x…>`.
        return f"{self.full_name} <{self.email}>"

    @property
    def can_host(self) -> bool:
        """An instructor can only host if they've connected a Google account —
        that's whose calendar the Meet link is created on."""
        return (
            self.role in (UserRole.INSTRUCTOR, UserRole.SUPERUSER)
            and self.google_credential is not None
        )


class GoogleCredential(Base, Timestamped):
    """An instructor's OAuth grant. We create the Calendar event (and therefore the
    Meet link) on *their* calendar so they are the real host of the meeting."""

    __tablename__ = "google_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    google_email: Mapped[str] = mapped_column(String(320), nullable=False)
    #: Fernet ciphertext — never store this in the clear.
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="google_credential")

    @property
    def is_usable(self) -> bool:
        return self.revoked_at is None

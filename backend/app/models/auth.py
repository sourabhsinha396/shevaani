from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey
from app.models.user import User


class EmailVerificationToken(Base, UUIDPrimaryKey):
    """A single-use, expiring proof that someone can read an address.

    Same shape as :class:`PasswordResetToken` and deliberately a separate table
    rather than one table with a ``purpose`` column: the two have different
    lifetimes, different blast radius if leaked, and a reset token that could be
    spent as a verification token (or the reverse) is exactly the kind of
    confusion a shared table invites.

    Verification is **advisory** — see ``services/verification.py``.
    """

    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Hex SHA-256 of the raw token.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: The address being proved, captured at send time. If the account's email
    #: changes before the link is opened, the token is for the old address and
    #: must not verify the new one.
    email: Mapped[str] = mapped_column(String(320), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship()

    def is_usable(self, now: datetime) -> bool:
        return self.used_at is None and self.expires_at > now


class PasswordResetToken(Base, UUIDPrimaryKey):
    """A single-use, expiring password reset grant.

    Only the SHA-256 of the token is stored. The token itself is 32 bytes of
    ``secrets`` output, so there is no dictionary to attack and a fast hash is
    the right choice — Argon2 here would cost a lot and buy nothing. What the
    hash does buy is that a database leak alone cannot reset anyone's password.

    Single use is ``used_at``, not deletion: a support question of the form "did
    someone use that link?" is answerable, and rows are cheap.
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Hex SHA-256 of the raw token. Unique, so a collision is a hard error
    #: rather than two users quietly sharing a reset link.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    #: Kept for abuse investigation. Rate limiting itself is ITC-53.
    requested_ip: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship()

    def is_usable(self, now: datetime) -> bool:
        return self.used_at is None and self.expires_at > now

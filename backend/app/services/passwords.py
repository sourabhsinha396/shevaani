"""Password reset and change.

Two rules shape everything in here.

**The reset endpoint must not be an account oracle.** Asking to reset an address
returns the same response whether or not it exists, takes the same path, and
never raises. That is why :func:`request_reset` returns ``None`` for every
outcome — there is no result for a caller to accidentally leak.

**Changing a password signs out every other browser.** Sessions are stateless
JWTs, so there is no session table to delete from; instead ``password_changed_at``
moves forward and :mod:`app.api.deps` refuses any token issued before it.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.integrations import email as email_service
from app.models.auth import PasswordResetToken
from app.models.user import User
from app.services.errors import DomainError
from app.services.scheduling import utc_now

#: 32 bytes of urlsafe base64. Long enough that guessing is not a threat model.
_TOKEN_BYTES = 32


class InvalidResetToken(DomainError):
    status_code = 400
    code = "invalid_reset_token"


class IncorrectPassword(DomainError):
    status_code = 400
    code = "incorrect_password"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def token_cutoff(user: User) -> int | None:
    """Whole seconds before which a JWT for this user is no longer accepted.

    JWT ``iat`` has one-second granularity, so this compares as ``iat < cutoff``
    and a token minted in the same second as the change survives. That one-second
    overlap is the safe direction to err in: the alternative rounds the *other*
    way and invalidates the token we hand back from the reset itself.
    """
    if user.password_changed_at is None:
        return None
    return int(user.password_changed_at.timestamp())


async def request_reset(db: AsyncSession, raw_email: str, *, ip: str | None = None) -> None:
    """Start a reset. Silent for unknown or disabled accounts, by design."""
    email = raw_email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return

    now = utc_now()

    # Supersede anything outstanding, so a forwarded older email stops working
    # the moment a new one is requested.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
            created_at=now,
            requested_ip=ip,
        )
    )
    await db.flush()

    await email_service.dispatch(
        email_service.build_password_reset(
            to=user.email, full_name=user.full_name, token=raw_token
        )
    )


async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> User:
    """Spend a reset token. Raises rather than returning a status — a failed
    reset has exactly one cause the caller can act on."""
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(raw_token))
    )
    token = result.scalar_one_or_none()
    now = utc_now()

    if token is None or not token.is_usable(now):
        raise InvalidResetToken("That reset link is invalid or has expired. Request a new one.")

    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise InvalidResetToken("That reset link is invalid or has expired. Request a new one.")

    token.used_at = now
    _apply_new_password(user, new_password, at=now)
    await db.flush()

    await email_service.dispatch(
        email_service.build_password_changed(to=user.email, full_name=user.full_name)
    )
    return user


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> User:
    if user.password_hash is None:
        # Google-created account: there is no current password to prove. The
        # forgot-password flow is the way to set a first one — same mailbox
        # proof, and it works signed out too.
        raise IncorrectPassword(
            "This account signs in with Google and has no password yet. "
            "Use “Forgot your password?” on the sign-in page to set one."
        )
    if not verify_password(current_password, user.password_hash):
        raise IncorrectPassword("That is not your current password.")

    now = utc_now()
    _apply_new_password(user, new_password, at=now)

    # A password change is also an implicit "lock everyone else out", so any
    # outstanding reset link dies with it.
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    await db.flush()

    await email_service.dispatch(
        email_service.build_password_changed(to=user.email, full_name=user.full_name)
    )
    return user


def _apply_new_password(user: User, new_password: str, *, at: datetime) -> None:
    user.password_hash = hash_password(new_password)
    user.password_changed_at = at


async def purge_expired_tokens(db: AsyncSession, older_than_days: int = 30) -> int:
    """Housekeeping for the worker. Spent and expired rows have no further use."""
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    result = await db.execute(
        select(PasswordResetToken.id).where(PasswordResetToken.created_at < cutoff)
    )
    ids: list[uuid.UUID] = [row[0] for row in result.all()]
    if ids:
        await db.execute(
            PasswordResetToken.__table__.delete().where(PasswordResetToken.id.in_(ids))
        )
    return len(ids)

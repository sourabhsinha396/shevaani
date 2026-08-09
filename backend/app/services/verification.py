"""Email verification.

**Verification is advisory. It does not gate booking.** ITC-50 left that open,
so the reasoning, for whoever revisits it:

* Credits are bought before they are spent. Gating booking on a verified address
  would take money and then refuse the thing the money buys, which is the worst
  possible time to discover a typo.
* The thing an unverified address actually costs is *reminders and session
  links*, and that lands on the learner who typed it. Making the consequence
  visible where the mistake is fixable — a banner with a resend button — is the
  proportionate response.
* Nothing here is a spam vector: an account with a wrong address cannot receive
  anything, so there is no abuse to prevent by blocking bookings.

What being unverified *does* change is on our side: an unverified address should
not be trusted for anything sensitive, and the send is throttled so the endpoint
cannot be used to mail someone repeatedly.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import email as email_service
from app.models.auth import EmailVerificationToken
from app.models.user import User
from app.services.errors import Conflict, DomainError
from app.services.scheduling import utc_now

_TOKEN_BYTES = 32

#: Long enough that a link found in an old inbox is useless, short enough that
#: nobody has to hurry. Verification is not a credential worth keeping alive.
TTL_HOURS = 48

#: Somebody who did not get the first one will ask again within a minute. Two
#: sends a minute is generous for that and useless as a way to bombard an inbox.
RESEND_INTERVAL_SECONDS = 30


class InvalidVerificationToken(DomainError):
    status_code = 400
    code = "invalid_verification_token"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def send_verification(db: AsyncSession, user: User) -> bool:
    """Issue a fresh link. Returns False if the address is already verified.

    Unlike the password-reset equivalent this is called by a signed-in user
    about their own address, so there is no oracle to protect and it can afford
    to tell the caller what happened.
    """
    if user.email_verified_at is not None:
        return False

    now = utc_now()

    recent = await db.execute(
        select(EmailVerificationToken.created_at)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.created_at
            > now - timedelta(seconds=RESEND_INTERVAL_SECONDS),
        )
        .limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        raise Conflict(
            "We've just sent one — give it a minute before asking again.",
            code="verification_throttled",
        )

    # Supersede anything outstanding so only the newest link works.
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            email=user.email,
            expires_at=now + timedelta(hours=TTL_HOURS),
            created_at=now,
        )
    )
    await db.flush()

    await email_service.dispatch(
        email_service.build_email_verification(
            to=user.email, full_name=user.full_name, token=raw_token
        )
    )
    return True


async def verify(db: AsyncSession, raw_token: str) -> User:
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == _hash_token(raw_token)
        )
    )
    token = result.scalar_one_or_none()
    now = utc_now()

    if token is None or not token.is_usable(now):
        raise InvalidVerificationToken(
            "That link is invalid or has expired. Send yourself a new one."
        )

    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise InvalidVerificationToken("That link is invalid or has expired.")

    # The token proves someone read `token.email`. If the account has moved on
    # to a different address since, that proof says nothing about the new one.
    if user.email != token.email:
        raise InvalidVerificationToken(
            "That link was sent to a different address than the one on this account."
        )

    token.used_at = now
    user.email_verified_at = now
    await db.flush()
    return user

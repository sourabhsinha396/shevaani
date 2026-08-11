"""Referrals — recorded at signup, credited at enrolment.

The promise on the page is "bring somebody, get a free session when they
enrol". Two moments matter and they are deliberately different:

* **Signup** (:func:`record_signup`): the ``?r=<code>`` the browser carried is
  resolved to its owner and a :class:`~app.models.referral.Referral` row is
  written. Nothing is granted. An unknown or malformed code is dropped
  silently — a typo in a shared link must not cost anyone their registration.
* **Enrolment** (:func:`credit_enrollment`): the referred person's first *paid*
  credit-pack purchase. That is when the referrer's free session lands.

Enrolment means money moved, on purpose. Crediting at signup would make the
reward farmable with a mailbox; crediting at first booking is nearly as weak
(welcome credit plus a cancel-refund loop); crediting at attendance hangs the
reward on a manual, delayed instructor action. The first settled payment is the
earliest signal that is real, and it already has exactly one choke point —
``billing.settle_paid`` — which calls this under the payment row lock.

The reward is "one session, whatever a session costs" — priced from
``settings.session_price_credits`` at credit time and frozen onto the row, so
repricing sessions later changes future rewards without rewriting history.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import CreditReason
from app.models.referral import Referral
from app.models.user import User
from app.services import credits
from app.services.scheduling import utc_now

#: Lowercase letters and digits minus the lookalikes (0/o, 1/l/i). These codes
#: get read off phone screens and retyped, so every character must survive that.
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 8


def _generate() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


async def unique_code(db: AsyncSession) -> str:
    """A referral code no user holds yet.

    31^8 ≈ 850 billion — a collision is a curiosity, but the column is UNIQUE
    and a signup that dies on it would be a real person refused an account over
    our own dice roll. Checking costs one indexed read.
    """
    while True:
        code = _generate()
        existing = await db.execute(select(User.id).where(User.referral_code == code))
        if existing.scalar_one_or_none() is None:
            return code


async def record_signup(db: AsyncSession, user: User, code: str | None) -> Referral | None:
    """Attribute a fresh signup to whoever's code it carried. Grants nothing.

    Every failure mode returns ``None`` rather than raising: the code rode in on
    a URL, and no state of it — mistyped, stale, the person's own — is worth
    failing a registration over.
    """
    if not code:
        return None
    code = code.strip().lower()
    if not code:
        return None

    result = await db.execute(
        select(User).where(User.referral_code == code, User.is_active.is_(True))
    )
    referrer = result.scalar_one_or_none()
    # `referrer.id == user.id` cannot happen for a fresh signup — their code was
    # minted this request — but this function has no reason to trust its caller.
    if referrer is None or referrer.id == user.id:
        return None

    referral = Referral(
        referrer_id=referrer.id,
        referred_user_id=user.id,
        code_used=code,
    )
    db.add(referral)
    await db.flush()
    return referral


async def credit_enrollment(db: AsyncSession, referred_user_id: uuid.UUID) -> Referral | None:
    """Grant the referrer their session if this person's enrolment is the first.

    Called from ``billing.settle_paid`` once a payment is PAID. The row lock
    taken here is what makes "exactly once" true even though two settlement
    paths (webhook and return-verify) can race: both would reach this, one gets
    the lock first and sets ``credited_at``, the other reads it and leaves.

    The grant is append-only and never *spends*, so the referrer's user row
    does not need locking — there is no balance check to race.
    """
    result = await db.execute(
        select(Referral)
        .where(
            Referral.referred_user_id == referred_user_id,
            Referral.credited_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        return None

    reward = settings.session_price_credits
    referral.credited_at = utc_now()
    referral.reward_credits = reward

    referred = await db.get(User, referred_user_id)
    # First name only — enough for "your friend enrolled" to read as news about
    # a person, without putting their full identity on somebody else's ledger.
    given = (referred.full_name.split() or ["Someone"])[0] if referred else "Someone"
    await credits.grant(
        db,
        referral.referrer_id,
        reward,
        CreditReason.REFERRAL_BONUS,
        note=f"{given} enrolled from your invite — a session on us",
    )
    await db.flush()
    return referral

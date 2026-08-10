"""Credit ledger.

Append-only. The balance is ``SUM(delta)`` — there is no mutable balance column,
so a bug can never silently corrupt someone's balance, only add a visible row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import CreditLedger
from app.models.enums import CreditReason
from app.models.user import User
from app.services.errors import InsufficientCredits
from app.services.scheduling import utc_now


async def balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(
            CreditLedger.user_id == user_id
        )
    )
    return int(result.scalar_one())


async def lock_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialise credit changes for one user so two bookings can't spend the same credit."""
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())


async def record(
    db: AsyncSession,
    user_id: uuid.UUID,
    delta: int,
    reason: CreditReason,
    *,
    booking_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    note: str | None = None,
    at: datetime | None = None,
) -> CreditLedger:
    entry = CreditLedger(
        user_id=user_id,
        delta=delta,
        reason=reason,
        booking_id=booking_id,
        payment_id=payment_id,
        note=note,
        created_at=at or utc_now(),
    )
    db.add(entry)
    await db.flush()
    return entry


async def spend(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    reason: CreditReason,
    *,
    booking_id: uuid.UUID | None = None,
    note: str | None = None,
) -> CreditLedger | None:
    """Deduct credits, refusing to go negative. Caller must hold ``lock_user``."""
    if amount == 0:
        return None
    current = await balance(db, user_id)
    if current < amount:
        # Unit-free on purpose. The ledger counts credits, but every screen a
        # learner sees counts sessions, and a session that overrides its
        # `price_credits` does not divide into a whole number of them — so
        # quoting either unit here would be wrong somewhere. The balance itself
        # is on screen already; what this needs to say is "not enough".
        raise InsufficientCredits(
            "You don't have enough left on your balance to book this session."
        )
    return await record(
        db, user_id, -amount, reason, booking_id=booking_id, note=note
    )


async def grant(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    reason: CreditReason,
    *,
    booking_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    note: str | None = None,
) -> CreditLedger | None:
    if amount == 0:
        return None
    return await record(
        db, user_id, amount, reason, booking_id=booking_id, payment_id=payment_id, note=note
    )

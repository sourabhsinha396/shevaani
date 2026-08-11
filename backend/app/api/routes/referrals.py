from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.referral import Referral
from app.models.user import User
from app.schemas.referrals import ReferralEntryOut, ReferralSummaryOut

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralSummaryOut)
async def my_referrals(db: DbSession, user: CurrentUser) -> ReferralSummaryOut:
    """The caller's own referral standing: code, who joined, what it earned.

    Strictly first-person — there is no ``/referrals/{user_id}``, and the names
    that appear here are reduced to given names. Whether those people bought
    anything is expressed only as "enrolled", never as an amount.
    """
    result = await db.execute(
        select(Referral, User.full_name)
        .join(User, User.id == Referral.referred_user_id)
        .where(Referral.referrer_id == user.id)
        .order_by(Referral.created_at.desc())
    )
    rows = result.all()

    entries = [
        ReferralEntryOut(
            first_name=(full_name.split() or ["Someone"])[0],
            joined_at=referral.created_at,
            enrolled_at=referral.credited_at,
            reward_credits=referral.reward_credits,
        )
        for referral, full_name in rows
    ]
    return ReferralSummaryOut(
        code=user.referral_code,
        reward_credits=settings.session_price_credits,
        total_joined=len(entries),
        total_enrolled=sum(1 for e in entries if e.enrolled_at is not None),
        credits_earned=sum(e.reward_credits for e in entries),
        referrals=entries,
    )

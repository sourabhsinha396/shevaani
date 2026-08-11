from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReferralEntryOut(BaseModel):
    """One person who joined through the caller's link.

    First name only — the referrer shared a link, not necessarily with somebody
    whose full identity they should now be shown. ``enrolled_at`` doubles as
    the status: NULL means joined but not yet enrolled.
    """

    first_name: str
    joined_at: datetime
    enrolled_at: datetime | None = None
    #: What this referral actually paid out, 0 until it does.
    reward_credits: int


class ReferralSummaryOut(BaseModel):
    code: str
    #: What one enrolment earns *now* — the page's copy says "a free session",
    #: and this is what that is worth in credits today.
    reward_credits: int
    total_joined: int
    total_enrolled: int
    credits_earned: int
    referrals: list[ReferralEntryOut]

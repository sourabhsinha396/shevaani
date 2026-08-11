from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.user import User


class Referral(Base, UUIDPrimaryKey, Timestamped):
    """One row per person who arrived through somebody's link.

    Written at signup, *credited* at enrolment: the referrer's reward is granted
    when the person they brought books something real, not when an email address
    is created. ``credited_at`` is what separates the two — NULL means "joined,
    hasn't enrolled yet", and the reward for a row is granted exactly once
    because crediting checks-and-sets it under a row lock.

    A person is referred at most once (unique on ``referred_user_id``), by
    whoever's code their signup actually carried. There is deliberately no
    "re-attribute" path — the ledger row the credit writes couldn't follow.
    """

    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
        CheckConstraint("referrer_id <> referred_user_id", name="not_self"),
    )

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    #: The code as the signup sent it (lowercased). Kept even though it is
    #: derivable from the referrer, so a code rotation later would not orphan
    #: the history of what was actually typed.
    code_used: Mapped[str] = mapped_column(String(32), nullable=False)

    #: When the referred learner enrolled and the reward was granted. NULL until
    #: then. Set once — the same check-and-set that grants the credits.
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: What the referrer was actually granted, frozen at credit time — the
    #: configured "one session" price can move later without rewriting history.
    reward_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    referrer: Mapped[User] = relationship(foreign_keys=[referrer_id])
    referred_user: Mapped[User] = relationship(foreign_keys=[referred_user_id])

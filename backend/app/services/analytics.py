"""Read-only aggregates for the admin's Analytics tab.

Everything here is a SELECT — this module must never write. Counts are computed
fresh on each request rather than maintained as counters; at this product's
size the queries are milliseconds, and a counter that drifts is worse than a
count that is slow.

Days are calendar days in the *business* timezone (``settings.booking_timezone``),
not UTC. An IST business day straddles two UTC dates, and a signup chart whose
"yesterday" disagrees with the operator's yesterday reads as a bug every time
it is looked at.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import CreditLedger, Payment
from app.models.booking import Booking
from app.models.enums import (
    SEAT_HOLDING_STATUSES,
    BookingStatus,
    CreditReason,
    PaymentStatus,
    UserRole,
)
from app.models.referral import Referral
from app.models.user import User
from app.schemas.admin import (
    AnalyticsDayOut,
    AnalyticsOut,
    AnalyticsTotalsOut,
    RevenueByCurrencyOut,
    TopReferrerOut,
)
from app.services.scheduling import utc_now


def _local_day(column):  # noqa: ANN001, ANN202 — SQLAlchemy column expressions
    """The business-timezone calendar date of a UTC timestamp column."""
    return cast(func.timezone(settings.booking_timezone, column), Date)


async def _count(db: AsyncSession, query) -> int:  # noqa: ANN001
    return int((await db.execute(query)).scalar_one() or 0)


async def _daily(db: AsyncSession, column, *conditions) -> dict[date, int]:  # noqa: ANN001
    day = _local_day(column)
    result = await db.execute(
        select(day, func.count()).where(*conditions).group_by(day)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def overview(db: AsyncSession, days: int) -> AnalyticsOut:
    now = utc_now()
    since = now - timedelta(days=days)

    learners = await _count(
        db, select(func.count(User.id)).where(User.role == UserRole.LEARNER)
    )
    new_learners = await _count(
        db,
        select(func.count(User.id)).where(
            User.role == UserRole.LEARNER, User.created_at >= since
        ),
    )
    bookings_confirmed = await _count(
        db,
        select(func.count(Booking.id)).where(
            Booking.created_at >= since, Booking.status.in_(SEAT_HOLDING_STATUSES)
        ),
    )
    bookings_cancelled = await _count(
        db,
        select(func.count(Booking.id)).where(
            Booking.created_at >= since, Booking.status == BookingStatus.CANCELLED
        ),
    )
    payments_paid = await _count(
        db,
        select(func.count(Payment.id)).where(
            Payment.status == PaymentStatus.PAID, Payment.paid_at >= since
        ),
    )
    credits_purchased = await _count(
        db,
        select(func.coalesce(func.sum(Payment.credits), 0)).where(
            Payment.status == PaymentStatus.PAID, Payment.paid_at >= since
        ),
    )
    credits_spent = await _count(
        db,
        select(func.coalesce(func.sum(-CreditLedger.delta), 0)).where(
            CreditLedger.reason == CreditReason.BOOKING_SPEND,
            CreditLedger.created_at >= since,
        ),
    )
    referrals_joined = await _count(
        db, select(func.count(Referral.id)).where(Referral.created_at >= since)
    )
    referrals_enrolled = await _count(
        db, select(func.count(Referral.id)).where(Referral.credited_at >= since)
    )
    referral_credits_awarded = await _count(
        db,
        select(func.coalesce(func.sum(Referral.reward_credits), 0)).where(
            Referral.credited_at >= since
        ),
    )

    revenue_rows = await db.execute(
        select(Payment.currency, func.sum(Payment.amount_minor), func.count(Payment.id))
        .where(Payment.status == PaymentStatus.PAID, Payment.paid_at >= since)
        .group_by(Payment.currency)
        .order_by(func.sum(Payment.amount_minor).desc())
    )
    revenue = [
        RevenueByCurrencyOut(currency=row[0], amount_minor=int(row[1]), payments=int(row[2]))
        for row in revenue_rows.all()
    ]

    signups_by_day = await _daily(
        db, User.created_at, User.role == UserRole.LEARNER, User.created_at >= since
    )
    bookings_by_day = await _daily(
        db,
        Booking.created_at,
        Booking.created_at >= since,
        Booking.status.in_(SEAT_HOLDING_STATUSES),
    )
    payments_by_day = await _daily(
        db,
        Payment.paid_at,
        Payment.status == PaymentStatus.PAID,
        Payment.paid_at >= since,
    )

    # Zero-filled through today: a day nothing happened is a data point, and a
    # chart that skips it silently compresses the quiet stretches.
    today = now.astimezone(settings.tz).date()
    first = today - timedelta(days=days - 1)
    series = [
        AnalyticsDayOut(
            date=day,
            signups=signups_by_day.get(day, 0),
            bookings=bookings_by_day.get(day, 0),
            payments=payments_by_day.get(day, 0),
        )
        for day in (first + timedelta(days=offset) for offset in range(days))
    ]

    enrolled_count = func.count(Referral.credited_at)
    top_rows = await db.execute(
        select(
            User.id,
            User.full_name,
            User.email,
            func.count(Referral.id),
            enrolled_count,
            func.coalesce(func.sum(Referral.reward_credits), 0),
        )
        .join(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(enrolled_count.desc(), func.count(Referral.id).desc())
        .limit(10)
    )
    top_referrers = [
        TopReferrerOut(
            user_id=row[0],
            full_name=row[1],
            email=row[2],
            joined=int(row[3]),
            enrolled=int(row[4]),
            credits_earned=int(row[5]),
        )
        for row in top_rows.all()
    ]

    return AnalyticsOut(
        days=days,
        totals=AnalyticsTotalsOut(
            learners=learners,
            new_learners=new_learners,
            bookings_confirmed=bookings_confirmed,
            bookings_cancelled=bookings_cancelled,
            payments_paid=payments_paid,
            credits_purchased=credits_purchased,
            credits_spent=credits_spent,
            referrals_joined=referrals_joined,
            referrals_enrolled=referrals_enrolled,
            referral_credits_awarded=referral_credits_awarded,
        ),
        revenue=revenue,
        series=series,
        top_referrers=top_referrers,
    )

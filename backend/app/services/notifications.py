"""Who gets told what, and when.

The mail *bodies* live in :mod:`app.integrations.email`. This module owns the
question one level up: given something that just happened to a session, which
learners need an email about it, and what does each of theirs say.

Keeping that here rather than in the booking service means the booking rules
stay readable — `cancel_session` is about seats and refunds, not about inboxes —
and it means every audience decision is in one file, which is where you want it
when someone asks "does the waitlist get the cancellation email too?" (they do:
they were counting on a session that is no longer happening, even though they
were never charged).

Reminders are the only thing in here with its own scheduling, and the important
part of them is that they read the session at send time. A job enqueued at
publish time carrying "starts at 18:00" would happily remind everybody about a
session that moved to Thursday.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.integrations import email as email_service
from app.models.booking import Booking
from app.models.enums import SEAT_HOLDING_STATUSES, BookingStatus, SessionStatus
from app.models.notifications import SessionReminder
from app.models.session import Session
from app.models.user import User
from app.services.scheduling import utc_now

logger = logging.getLogger(__name__)

#: How far past an offset a reminder is still worth sending. A worker that was
#: down for ten minutes should still send the 24h reminder; one that was down for
#: three hours should not send the "starts in an hour" mail after it started.
_LATE_TOLERANCE = timedelta(minutes=20)


async def _live_bookings(db: AsyncSession, session_id: uuid.UUID, *, include_waitlist: bool):
    statuses = list(SEAT_HOLDING_STATUSES)
    if include_waitlist:
        statuses.append(BookingStatus.WAITLISTED)
    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.learner))
        .where(Booking.session_id == session_id, Booking.status.in_(statuses))
    )
    return list(result.scalars().all())


# ----------------------------------------------------------------- reminders


async def send_due_reminders(db: AsyncSession, hours_before: int) -> int:
    """Send the ``hours_before`` reminder for every session now due one.

    Returns the number of sessions reminded, not the number of emails — the
    caller logs it, and "3 sessions" is the useful number when reading worker
    output.
    """
    now = utc_now()
    target = now + timedelta(hours=hours_before)

    result = await db.execute(
        select(Session).where(
            Session.status == SessionStatus.PUBLISHED,
            # Both bounds matter. Without the lower one a restart would fire
            # every reminder it ever missed; without the upper one nothing is
            # ever due.
            Session.starts_at > target - _LATE_TOLERANCE,
            Session.starts_at <= target,
            Session.id.not_in(
                select(SessionReminder.session_id).where(
                    SessionReminder.hours_before == hours_before
                )
            ),
        )
    )
    sessions = list(result.scalars().all())

    reminded = 0
    for session in sessions:
        # Claim the send before doing it. Two workers racing here both pass the
        # NOT IN above; only one survives the unique constraint, and the loser
        # must not also mail everyone.
        marker = SessionReminder(
            session_id=session.id, hours_before=hours_before, sent_at=now, recipients=0
        )
        db.add(marker)
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            continue

        bookings = await _live_bookings(db, session.id, include_waitlist=False)
        for booking in bookings:
            learner = booking.learner
            await email_service.dispatch(
                email_service.build_session_reminder(
                    to=learner.email,
                    full_name=learner.full_name,
                    timezone=learner.timezone,
                    title=session.title,
                    starts_at=session.starts_at,
                    hours_before=hours_before,
                )
            )
        marker.recipients = len(bookings)
        reminded += 1

    await db.flush()
    return reminded


# -------------------------------------------------------------- cancellation


async def session_cancelled(
    db: AsyncSession,
    session: Session,
    bookings: list[Booking],
    *,
    automatic: bool,
    reason: str,
) -> int:
    """Tell everyone a session is off.

    ``bookings`` is what the cancellation actually touched, passed in rather than
    re-queried: by the time this runs those rows are already CANCELLED, so a
    fresh query would find nobody. ``credits_spent`` on them is likewise the
    pre-cancellation figure, which is exactly the number that was refunded.
    """
    learner_ids = [b.learner_id for b in bookings]
    if not learner_ids:
        return 0

    result = await db.execute(select(User).where(User.id.in_(learner_ids)))
    learners = {u.id: u for u in result.scalars().all()}

    for booking in bookings:
        learner = learners.get(booking.learner_id)
        if learner is None:
            continue
        if automatic:
            message = email_service.build_session_auto_cancelled(
                to=learner.email,
                full_name=learner.full_name,
                timezone=learner.timezone,
                title=session.title,
                starts_at=session.starts_at,
                credits_refunded=booking.credits_spent,
            )
        else:
            message = email_service.build_session_cancelled_by_us(
                to=learner.email,
                full_name=learner.full_name,
                timezone=learner.timezone,
                title=session.title,
                starts_at=session.starts_at,
                reason=reason,
                credits_refunded=booking.credits_spent,
            )
        await email_service.dispatch(message)
    return len(bookings)


async def booking_cancelled(
    db: AsyncSession, booking: Booking, *, credits_refunded: int
) -> None:
    """Learner-initiated. Reads differently from the two above on purpose — they
    are apologies, this is a receipt for something they chose."""
    learner = await db.get(User, booking.learner_id)
    session = await db.get(Session, booking.session_id)
    if learner is None or session is None:
        return
    await email_service.dispatch(
        email_service.build_booking_cancelled(
            to=learner.email,
            full_name=learner.full_name,
            timezone=learner.timezone,
            title=session.title,
            starts_at=session.starts_at,
            credits_refunded=credits_refunded,
        )
    )


# ------------------------------------------------------------------ waitlist


async def waitlist_promoted(db: AsyncSession, session: Session, bookings: list[Booking]) -> None:
    """Promotion spends a credit without the learner doing anything. Silence here
    means the first they hear of it is a balance that dropped on its own."""
    for booking in bookings:
        learner = await db.get(User, booking.learner_id)
        if learner is None:
            continue
        await email_service.dispatch(
            email_service.build_waitlist_promoted(
                to=learner.email,
                full_name=learner.full_name,
                timezone=learner.timezone,
                title=session.title,
                starts_at=session.starts_at,
                credits_spent=booking.credits_spent,
            )
        )


# ------------------------------------------------------------------- billing


async def credit_receipt(db: AsyncSession, payment) -> None:
    """Sent from the webhook handler, once the money is confirmed — never from
    the buyer's return to the success page."""
    learner = await db.get(User, payment.user_id)
    if learner is None:
        return
    await email_service.dispatch(
        email_service.build_credit_receipt(
            to=learner.email,
            full_name=learner.full_name,
            credits=payment.credits,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            provider=payment.provider.value,
            payment_id=str(payment.id),
        )
    )


def configured_reminder_offsets() -> list[int]:
    """Deduplicated and sorted, so a stray ``[24, 24, 1]`` in the environment
    does not mail everybody twice."""
    return sorted({h for h in settings.session_reminder_hours if h > 0}, reverse=True)

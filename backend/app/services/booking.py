"""Booking — seats, waitlist, cancellation, refunds.

Lock ordering, to keep deadlocks out: **session row first, then the learner's
user row.** One-to-one booking creates the session, so it takes the instructor
lock first (via ``scheduling.lock_instructor``) and the learner lock second.
Always acquire in that order.

Because credits are pre-purchased, a booking that clears the credit check is
confirmed immediately — there is no payment round-trip in the booking path.
``PENDING``/``hold_expires_at`` exist for a future per-session checkout flow and
are swept by :func:`release_expired_holds`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.enums import (
    SEAT_HOLDING_STATUSES,
    BookingStatus,
    CreditReason,
    SessionKind,
    SessionStatus,
)
from app.models.session import Session
from app.models.user import User
from app.services import credits, notifications, scheduling
from app.services.errors import Conflict, NotFound, SchedulingError, SessionFull
from app.services.scheduling import utc_now


async def lock_session(db: AsyncSession, session_id: uuid.UUID) -> Session:
    """Fetch a session with its row locked. Everything seat-related goes through here."""
    result = await db.execute(select(Session).where(Session.id == session_id).with_for_update())
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFound("Session not found.")
    return session


async def seats_taken(db: AsyncSession, session_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.session_id == session_id,
            Booking.status.in_(SEAT_HOLDING_STATUSES),
        )
    )
    return int(result.scalar_one())


async def existing_booking(
    db: AsyncSession, session_id: uuid.UUID, learner_id: uuid.UUID
) -> Booking | None:
    result = await db.execute(
        select(Booking).where(
            Booking.session_id == session_id,
            Booking.learner_id == learner_id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )
    return result.scalars().first()


async def book_group_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    learner: User,
    *,
    allow_waitlist: bool = True,
) -> Booking:
    session = await lock_session(db, session_id)

    if session.kind != SessionKind.GROUP:
        raise Conflict("That is not a group discussion.")
    if session.status != SessionStatus.PUBLISHED:
        raise Conflict("This session is not open for booking.")
    if session.starts_at <= utc_now():
        raise Conflict("This session has already started.")

    if await existing_booking(db, session.id, learner.id) is not None:
        raise Conflict("You have already booked this session.")

    await credits.lock_user(db, learner.id)

    taken = await seats_taken(db, session.id)
    if taken >= session.max_seats:
        if not allow_waitlist:
            raise SessionFull("This session is full.")
        return await _add_to_waitlist(db, session, learner)

    booking = Booking(
        session_id=session.id,
        learner_id=learner.id,
        status=BookingStatus.CONFIRMED,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        credits_spent=session.price_credits,
    )
    db.add(booking)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict(_explain_booking_conflict(exc)) from exc

    await credits.spend(
        db,
        learner.id,
        session.price_credits,
        CreditReason.BOOKING_SPEND,
        booking_id=booking.id,
        note=session.title,
    )
    return booking


async def _add_to_waitlist(db: AsyncSession, session: Session, learner: User) -> Booking:
    """Waitlisted bookings don't spend credits — they're charged on promotion."""
    result = await db.execute(
        select(func.coalesce(func.max(Booking.waitlist_position), 0)).where(
            Booking.session_id == session.id,
            Booking.status == BookingStatus.WAITLISTED,
        )
    )
    position = int(result.scalar_one()) + 1

    booking = Booking(
        session_id=session.id,
        learner_id=learner.id,
        status=BookingStatus.WAITLISTED,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        credits_spent=0,
        waitlist_position=position,
    )
    db.add(booking)
    await db.flush()
    return booking


async def book_one_on_one(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    learner: User,
    starts_at: datetime,
    *,
    duration_minutes: int | None = None,
    title: str | None = None,
    price_credits: int = 1,
) -> tuple[Session, Booking]:
    """Create the one-to-one session and the learner's booking in one transaction."""
    duration = timedelta(minutes=duration_minutes or settings.one_on_one_slot_minutes)
    ends_at = starts_at + duration

    instructor = await db.get(User, instructor_id)
    if instructor is None or not instructor.is_active:
        raise NotFound("Instructor not found.")

    # Lock order: instructor, then learner.
    await scheduling.lock_instructor(db, instructor_id)
    await scheduling.assert_instructor_available(
        db, instructor_id, starts_at, ends_at, kind=SessionKind.ONE_ON_ONE
    )
    await credits.lock_user(db, learner.id)

    session = Session(
        kind=SessionKind.ONE_ON_ONE,
        status=SessionStatus.PUBLISHED,
        title=title or f"1:1 with {instructor.full_name}",
        starts_at=starts_at,
        ends_at=ends_at,
        min_seats=1,
        max_seats=1,
        price_credits=price_credits,
        instructor_id=instructor_id,
        created_by_id=learner.id,
    )
    db.add(session)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SchedulingError(
            "That slot was taken while you were booking. Please pick another."
        ) from exc

    booking = Booking(
        session_id=session.id,
        learner_id=learner.id,
        status=BookingStatus.CONFIRMED,
        starts_at=starts_at,
        ends_at=ends_at,
        credits_spent=price_credits,
    )
    db.add(booking)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict(_explain_booking_conflict(exc)) from exc

    await credits.spend(
        db,
        learner.id,
        price_credits,
        CreditReason.BOOKING_SPEND,
        booking_id=booking.id,
        note=session.title,
    )
    return session, booking


def _refund_due(session: Session, at: datetime | None = None) -> bool:
    at = at or utc_now()
    cutoff = session.starts_at - timedelta(hours=settings.cancellation_full_refund_hours)
    return at <= cutoff


async def cancel_booking(
    db: AsyncSession,
    booking: Booking,
    *,
    reason: str | None = None,
    force_refund: bool = False,
) -> Booking:
    """Cancel and, if inside the refund window, return the credits."""
    if booking.status == BookingStatus.CANCELLED:
        return booking

    session = await lock_session(db, booking.session_id)
    await credits.lock_user(db, booking.learner_id)

    refund = booking.credits_spent > 0 and (force_refund or _refund_due(session))
    refunded = booking.credits_spent if refund else 0

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = utc_now()
    booking.cancellation_reason = reason
    booking.waitlist_position = None

    if refund:
        await credits.grant(
            db,
            booking.learner_id,
            booking.credits_spent,
            CreditReason.SESSION_CANCELLED if force_refund else CreditReason.BOOKING_REFUND,
            booking_id=booking.id,
            note=session.title,
        )
    await db.flush()

    await notifications.booking_cancelled(db, booking, credits_refunded=refunded)

    if session.kind == SessionKind.GROUP and session.status == SessionStatus.PUBLISHED:
        promoted = await promote_from_waitlist(db, session)
        await notifications.waitlist_promoted(db, session, promoted)
    return booking


async def record_attendance(db: AsyncSession, booking: Booking, *, attended: bool) -> Booking:
    """Instructor-confirmed attendance.

    `conferenceRecords` is Workspace-only (PLAN decision 7), so join-clicks are
    the automatic signal and this is the authoritative correction. A cancelled
    booking is never resurrected by it — someone who cancelled and then had the
    session marked "attended" would look like they spent a credit they got back.
    """
    if booking.status == BookingStatus.CANCELLED:
        raise Conflict("That booking was cancelled — attendance can't be recorded for it.")
    booking.status = BookingStatus.ATTENDED if attended else BookingStatus.NO_SHOW
    booking.attendance_confirmed_at = utc_now()
    await db.flush()
    return booking


async def cancellation_impact(db: AsyncSession, session: Session) -> dict[str, int]:
    """What cancelling this session would cost, for the confirm dialog.

    Session cancellation refunds every live booking regardless of the usual
    cutoff, so this is exactly the sum of what has been spent on it.
    """
    result = await db.execute(
        select(Booking).where(
            Booking.session_id == session.id,
            Booking.status.in_([*SEAT_HOLDING_STATUSES, BookingStatus.WAITLISTED]),
        )
    )
    affected = list(result.scalars().all())
    return {
        "bookings_affected": len(affected),
        "learners_refunded": sum(1 for b in affected if b.credits_spent > 0),
        "credits_refunded": sum(b.credits_spent for b in affected),
        "waitlisted": sum(1 for b in affected if b.status == BookingStatus.WAITLISTED),
    }


async def promote_from_waitlist(db: AsyncSession, session: Session) -> list[Booking]:
    """Fill freed seats from the waitlist, in order.

    A candidate can fail for two reasons — no credits, or they've since booked
    something that overlaps (the exclusion constraint catches that). Either way
    we skip them and try the next, inside a savepoint so one failure doesn't
    poison the transaction.
    """
    promoted: list[Booking] = []
    free = session.max_seats - await seats_taken(db, session.id)
    if free <= 0:
        return promoted

    result = await db.execute(
        select(Booking)
        .where(
            Booking.session_id == session.id,
            Booking.status == BookingStatus.WAITLISTED,
        )
        .order_by(Booking.waitlist_position)
    )
    candidates = list(result.scalars().all())

    for candidate in candidates:
        if free <= 0:
            break
        try:
            async with db.begin_nested():
                await credits.lock_user(db, candidate.learner_id)
                await credits.spend(
                    db,
                    candidate.learner_id,
                    session.price_credits,
                    CreditReason.BOOKING_SPEND,
                    booking_id=candidate.id,
                    note=f"{session.title} (from waitlist)",
                )
                candidate.status = BookingStatus.CONFIRMED
                candidate.credits_spent = session.price_credits
                candidate.waitlist_position = None
                await db.flush()
        except Exception:  # noqa: BLE001 — a skipped candidate must not fail the request
            continue
        promoted.append(candidate)
        free -= 1

    return promoted


async def cancel_session(
    db: AsyncSession,
    session: Session,
    *,
    reason: str,
    automatic: bool = False,
) -> list[Booking]:
    """Cancel a session and refund every live booking regardless of the cutoff.

    ``automatic`` distinguishes the T-2h under-filled sweep from a superuser
    deciding to pull a session. Both refund identically; they read completely
    differently to the learner, and telling someone "not enough people booked"
    when a human cancelled it is a small lie that costs trust.
    """
    session.status = SessionStatus.CANCELLED
    session.cancelled_at = utc_now()
    session.cancellation_reason = reason

    result = await db.execute(
        select(Booking).where(
            Booking.session_id == session.id,
            Booking.status.in_([*SEAT_HOLDING_STATUSES, BookingStatus.WAITLISTED]),
        )
    )
    affected = list(result.scalars().all())

    for booking in affected:
        await credits.lock_user(db, booking.learner_id)
        if booking.credits_spent > 0:
            await credits.grant(
                db,
                booking.learner_id,
                booking.credits_spent,
                CreditReason.SESSION_CANCELLED,
                booking_id=booking.id,
                note=session.title,
            )
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = utc_now()
        booking.cancellation_reason = reason
        booking.waitlist_position = None

    await db.flush()

    # Dispatched after the rows are settled, and given `affected` rather than a
    # fresh query — those bookings are CANCELLED now, so re-reading them would
    # find nobody to write to.
    await notifications.session_cancelled(
        db, session, affected, automatic=automatic, reason=reason
    )
    return affected


async def release_expired_holds(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Sweeper for the future per-session checkout flow. No-op under the credit model."""
    now = now or utc_now()
    result = await db.execute(
        select(Booking).where(
            Booking.status == BookingStatus.PENDING,
            Booking.hold_expires_at.is_not(None),
            Booking.hold_expires_at < now,
        )
    )
    expired = list(result.scalars().all())
    for booking in expired:
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        booking.cancellation_reason = "Payment hold expired"
    await db.flush()
    return len(expired)


def _explain_booking_conflict(exc: IntegrityError) -> str:
    """Turn a constraint name into something a learner can act on."""
    detail = str(getattr(exc, "orig", exc))
    if "ex_bookings_learner_no_overlap" in detail:
        return "You already have another session booked at this time."
    if "uq_bookings_session_learner_active" in detail:
        return "You have already booked this session."
    return "That booking conflicts with an existing one."

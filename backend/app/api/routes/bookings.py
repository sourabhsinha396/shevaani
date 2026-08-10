from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.api.ratelimit import limiter
from app.api.serializers import build_one_on_one_out, build_session_out, seat_counts
from app.core.config import settings
from app.core.ratelimit import BOOKING
from app.models.billing import CreditLedger
from app.models.booking import Booking
from app.models.enums import SEAT_HOLDING_STATUSES, BookingStatus, SessionStatus
from app.models.session import OneOnOneSession, Session, SessionMeeting
from app.schemas.booking import (
    BookingOut,
    BookingWithSessionOut,
    CancelBookingIn,
    CreditBalanceOut,
    LedgerEntryOut,
    OneOnOneBookIn,
)
from app.services import booking as booking_service
from app.services import credits
from app.services.errors import NotFound, PermissionDenied
from app.services.scheduling import utc_now
from app.workers import queue

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _join_url_for(
    booking: Booking,
    session: Session | OneOnOneSession,
    meeting: SessionMeeting | None,
    now: datetime,
) -> str | None:
    """The Meet link for the caller's own booking, or None if there isn't one yet.

    How long there is until the session is deliberately *not* a condition. A
    Meet room lets nobody in before its host arrives, so a link handed over
    early opens onto a lobby and nothing else — holding it back until fifteen
    minutes before the hour protected nothing and left the learner with a page
    that could not answer "where do I go?".

    What is still a condition: a seat (the waitlist has no room to enter), a
    session that is still happening, a meeting the worker has actually made, and
    an hour that has not already passed.
    """
    if booking.status not in SEAT_HOLDING_STATUSES:
        return None
    if session.status == SessionStatus.CANCELLED:
        return None
    if meeting is None or not meeting.is_ready:
        return None
    if now > booking.ends_at + timedelta(minutes=settings.join_window_after_minutes):
        return None
    return meeting.join_url


@router.get("", response_model=list[BookingWithSessionOut])
async def my_bookings(
    db: DbSession,
    user: CurrentUser,
    upcoming: Annotated[bool, Query()] = True,
) -> list[BookingWithSessionOut]:
    """Everything the caller has booked, of both kinds, newest hour first.

    Both parents are eager-loaded because a booking hangs off exactly one of
    them and which one is per row — a lazy load here would be an N+1 on the
    page a signed-in learner opens most.
    """
    conditions = [
        Booking.learner_id == user.id,
        Booking.status != BookingStatus.CANCELLED,
    ]
    if upcoming:
        conditions.append(Booking.ends_at > utc_now())

    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.session).selectinload(Session.instructor),
            selectinload(Booking.session).selectinload(Session.meeting),
            selectinload(Booking.one_on_one).selectinload(OneOnOneSession.instructor),
            selectinload(Booking.one_on_one).selectinload(OneOnOneSession.meeting),
        )
        .where(*conditions)
        .order_by(Booking.starts_at)
    )
    bookings = list(result.scalars().all())

    now = utc_now()
    taken = await seat_counts(db, [b.session_id for b in bookings if b.session_id])

    out: list[BookingWithSessionOut] = []
    for b in bookings:
        if b.session is not None:
            parent: Session | OneOnOneSession = b.session
            session_out = build_session_out(
                b.session, taken=taken.get(b.session_id, 0), my_status=b.status
            )
        elif b.one_on_one is not None:
            parent = b.one_on_one
            session_out = build_one_on_one_out(b.one_on_one, my_status=b.status)
        else:  # pragma: no cover — ck_bookings_exactly_one_parent forbids it
            continue

        meeting = parent.meeting
        out.append(
            BookingWithSessionOut(
                id=b.id,
                session_id=b.parent_id,
                status=b.status,
                starts_at=b.starts_at,
                ends_at=b.ends_at,
                credits_spent=b.credits_spent,
                waitlist_position=b.waitlist_position,
                session=session_out,
                join_url=_join_url_for(b, parent, meeting, now),
                meeting_status=meeting.status if meeting else None,
            )
        )
    return out


@router.post(
    "/one-on-one",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limiter("book", BOOKING))],
)
async def book_one_on_one(
    payload: OneOnOneBookIn,
    db: DbSession,
    user: CurrentUser,
) -> BookingOut:
    """Book a one-to-one.

    The session row is created here, so the booking window (07:00-19:00 IST),
    the one-hour buffer, and the instructor's blocked time are all checked
    under an instructor row lock before anything is written.
    """
    session, booking = await booking_service.book_one_on_one(
        db,
        payload.instructor_id,
        user,
        payload.starts_at,
        duration_minutes=payload.duration_minutes,
    )
    # Commit before enqueuing — a worker must never see a job for a rolled-back row.
    await db.commit()
    await queue.enqueue("sync_session_meeting", str(session.id))
    return BookingOut.model_validate(booking)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: uuid.UUID,
    payload: CancelBookingIn,
    db: DbSession,
    user: CurrentUser,
) -> BookingOut:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise NotFound("Booking not found.")
    if booking.learner_id != user.id:
        raise PermissionDenied("That isn't your booking.")

    updated = await booking_service.cancel_booking(db, booking, reason=payload.reason)
    return BookingOut.model_validate(updated)


@router.get("/credits/balance", response_model=CreditBalanceOut)
async def credit_balance(db: DbSession, user: CurrentUser) -> CreditBalanceOut:
    return CreditBalanceOut(balance=await credits.balance(db, user.id))


@router.get("/credits/ledger", response_model=list[LedgerEntryOut])
async def credit_ledger(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LedgerEntryOut]:
    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.user_id == user.id)
        .order_by(CreditLedger.created_at.desc())
        .limit(limit)
    )
    return [
        LedgerEntryOut(
            id=e.id,
            delta=e.delta,
            reason=e.reason.value,
            note=e.note,
            created_at=e.created_at,
        )
        for e in result.scalars().all()
    ]

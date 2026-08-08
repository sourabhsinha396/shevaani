from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import build_session_out, seat_counts
from app.models.billing import CreditLedger
from app.models.booking import Booking
from app.models.enums import BookingStatus
from app.models.session import Session
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


@router.get("", response_model=list[BookingWithSessionOut])
async def my_bookings(
    db: DbSession,
    user: CurrentUser,
    upcoming: Annotated[bool, Query()] = True,
) -> list[BookingWithSessionOut]:
    conditions = [
        Booking.learner_id == user.id,
        Booking.status != BookingStatus.CANCELLED,
    ]
    if upcoming:
        conditions.append(Booking.ends_at > utc_now())

    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.session).selectinload(Session.instructor))
        .where(*conditions)
        .order_by(Booking.starts_at)
    )
    bookings = list(result.scalars().all())

    taken = await seat_counts(db, [b.session_id for b in bookings])
    return [
        BookingWithSessionOut(
            id=b.id,
            session_id=b.session_id,
            status=b.status,
            starts_at=b.starts_at,
            ends_at=b.ends_at,
            credits_spent=b.credits_spent,
            waitlist_position=b.waitlist_position,
            session=build_session_out(
                b.session, taken=taken.get(b.session_id, 0), my_status=b.status
            ),
        )
        for b in bookings
    ]


@router.post("/one-on-one", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
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

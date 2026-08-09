"""Shared read-model helpers.

Seat counts are computed in one grouped query rather than per row — the
catalogue is the hottest endpoint on the site and N+1 counting there would be
felt immediately.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking
from app.models.enums import SEAT_HOLDING_STATUSES, BookingStatus
from app.models.session import Session
from app.schemas.common import InstructorOut
from app.schemas.session import SessionAdminOut, SessionOut


async def seat_counts(
    db: AsyncSession, session_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not session_ids:
        return {}
    result = await db.execute(
        select(Booking.session_id, func.count(Booking.id))
        .where(
            Booking.session_id.in_(session_ids),
            Booking.status.in_(SEAT_HOLDING_STATUSES),
        )
        .group_by(Booking.session_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def waitlist_counts(
    db: AsyncSession, session_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not session_ids:
        return {}
    result = await db.execute(
        select(Booking.session_id, func.count(Booking.id))
        .where(
            Booking.session_id.in_(session_ids),
            Booking.status == BookingStatus.WAITLISTED,
        )
        .group_by(Booking.session_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def my_booking_statuses(
    db: AsyncSession, session_ids: Sequence[uuid.UUID], learner_id: uuid.UUID | None
) -> dict[uuid.UUID, BookingStatus]:
    if not session_ids or learner_id is None:
        return {}
    result = await db.execute(
        select(Booking.session_id, Booking.status).where(
            Booking.session_id.in_(session_ids),
            Booking.learner_id == learner_id,
            Booking.status != BookingStatus.CANCELLED,
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def session_roster(
    db: AsyncSession, session_id: uuid.UUID, *, include_emails: bool = True
) -> dict:
    """Who is in the room, and who is next in line.

    Shared by the superuser admin and the instructor's own view — the two must
    not be allowed to disagree about who is on the list. They differ in exactly
    one respect: an instructor gets names and levels, not contact details, which
    is what the privacy policy promises learners. That is enforced by leaving the
    address out of the payload, not by hiding a column in the UI.
    """
    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.learner))
        .where(Booking.session_id == session_id, Booking.status != BookingStatus.CANCELLED)
        .order_by(Booking.status, Booking.waitlist_position, Booking.created_at)
    )
    bookings = list(result.scalars().all())
    return {
        "confirmed": [
            {
                "booking_id": str(b.id),
                "learner_id": str(b.learner_id),
                "name": b.learner.full_name,
                "email": b.learner.email if include_emails else None,
                "level": b.learner.level.value if b.learner.level else None,
                "status": b.status.value,
                "first_joined_at": b.first_joined_at,
                "attendance_confirmed_at": b.attendance_confirmed_at,
            }
            for b in bookings
            if b.status != BookingStatus.WAITLISTED
        ],
        "waitlist": [
            {
                "booking_id": str(b.id),
                "learner_id": str(b.learner_id),
                "name": b.learner.full_name,
                "position": b.waitlist_position,
            }
            for b in bookings
            if b.status == BookingStatus.WAITLISTED
        ],
    }


def build_session_out(
    session: Session,
    *,
    taken: int,
    my_status: BookingStatus | None = None,
) -> SessionOut:
    return SessionOut(
        id=session.id,
        kind=session.kind,
        title=session.title,
        topic=session.topic,
        description=session.description,
        prep_material_url=session.prep_material_url,
        level_min=session.level_min,
        level_max=session.level_max,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        min_seats=session.min_seats,
        max_seats=session.max_seats,
        price_credits=session.price_credits,
        status=session.status,
        instructor=InstructorOut.model_validate(session.instructor),
        seats_taken=taken,
        seats_left=max(session.max_seats - taken, 0),
        is_full=taken >= session.max_seats,
        my_booking_status=my_status,
    )


def build_session_admin_out(
    session: Session,
    *,
    taken: int,
    waitlisted: int,
) -> SessionAdminOut:
    base = build_session_out(session, taken=taken)
    meeting = session.meeting
    return SessionAdminOut(
        **base.model_dump(),
        meeting_status=meeting.status if meeting else None,
        meeting_last_error=meeting.last_error if meeting else None,
        meeting_host_email=meeting.host_google_email if meeting else None,
        waitlist_count=waitlisted,
    )


async def serialize_sessions(
    db: AsyncSession,
    sessions: Sequence[Session],
    *,
    learner_id: uuid.UUID | None = None,
) -> list[SessionOut]:
    ids = [s.id for s in sessions]
    taken = await seat_counts(db, ids)
    mine = await my_booking_statuses(db, ids, learner_id)
    return [
        build_session_out(s, taken=taken.get(s.id, 0), my_status=mine.get(s.id))
        for s in sessions
    ]

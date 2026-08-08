"""Superuser session management.

Every mutation re-checks the role here — the frontend `/admin` guard is UX, not
security.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, Superuser
from app.api.serializers import build_session_admin_out, seat_counts, waitlist_counts
from app.models.booking import Booking
from app.models.enums import BookingStatus, SessionKind, SessionStatus, UserRole
from app.models.session import Session
from app.models.user import GoogleCredential, User
from app.schemas.common import Message
from app.schemas.session import (
    CancelIn,
    GroupSessionCreateIn,
    GroupSessionUpdateIn,
    RescheduleIn,
    SessionAdminOut,
)
from app.services import booking as booking_service
from app.services import session_admin
from app.services.errors import NotFound
from app.services.scheduling import utc_now
from app.workers import queue

router = APIRouter(prefix="/admin", tags=["admin"])


async def _load(db: DbSession, session_id: uuid.UUID) -> Session:
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.instructor), selectinload(Session.meeting))
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFound("Session not found.")
    return session


async def _serialize(db: DbSession, session: Session) -> SessionAdminOut:
    taken = await seat_counts(db, [session.id])
    waiting = await waitlist_counts(db, [session.id])
    return build_session_admin_out(
        session, taken=taken.get(session.id, 0), waitlisted=waiting.get(session.id, 0)
    )


@router.get("/sessions", response_model=list[SessionAdminOut])
async def list_sessions(
    db: DbSession,
    _: Superuser,
    kind: Annotated[SessionKind | None, Query()] = None,
    session_status: Annotated[SessionStatus | None, Query(alias="status")] = None,
    starts_after: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SessionAdminOut]:
    conditions = []
    if kind is not None:
        conditions.append(Session.kind == kind)
    if session_status is not None:
        conditions.append(Session.status == session_status)
    if starts_after is not None:
        conditions.append(Session.starts_at >= starts_after)

    result = await db.execute(
        select(Session)
        .options(selectinload(Session.instructor), selectinload(Session.meeting))
        .where(*conditions)
        .order_by(Session.starts_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = list(result.scalars().all())

    ids = [s.id for s in sessions]
    taken = await seat_counts(db, ids)
    waiting = await waitlist_counts(db, ids)
    return [
        build_session_admin_out(
            s, taken=taken.get(s.id, 0), waitlisted=waiting.get(s.id, 0)
        )
        for s in sessions
    ]


@router.post(
    "/sessions", response_model=SessionAdminOut, status_code=status.HTTP_201_CREATED
)
async def create_group_session(
    payload: GroupSessionCreateIn, db: DbSession, actor: Superuser
) -> SessionAdminOut:
    session = await session_admin.create_group_session(
        db,
        created_by=actor,
        instructor_id=payload.instructor_id,
        title=payload.title,
        topic=payload.topic,
        description=payload.description,
        prep_material_url=payload.prep_material_url,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        min_seats=payload.min_seats,
        max_seats=payload.max_seats,
        price_credits=payload.price_credits,
        level_min=payload.level_min,
        level_max=payload.level_max,
        publish=payload.publish,
    )
    session_id = session.id
    await db.commit()

    # Only published sessions need a Meet link; drafts get one when published.
    if payload.publish:
        await queue.enqueue("sync_session_meeting", str(session_id))

    return await _serialize(db, await _load(db, session_id))


@router.patch("/sessions/{session_id}", response_model=SessionAdminOut)
async def update_group_session(
    session_id: uuid.UUID,
    payload: GroupSessionUpdateIn,
    db: DbSession,
    _: Superuser,
) -> SessionAdminOut:
    session = await _load(db, session_id)
    await session_admin.update_group_session(
        db,
        session,
        title=payload.title,
        topic=payload.topic,
        description=payload.description,
        prep_material_url=payload.prep_material_url,
        level_min=payload.level_min,
        level_max=payload.level_max,
        min_seats=payload.min_seats,
        max_seats=payload.max_seats,
        price_credits=payload.price_credits,
    )
    await db.commit()

    # Title and description are mirrored into the calendar event.
    await queue.enqueue("sync_session_meeting", str(session_id))
    return await _serialize(db, await _load(db, session_id))


@router.post("/sessions/{session_id}/publish", response_model=SessionAdminOut)
async def publish_session(session_id: uuid.UUID, db: DbSession, _: Superuser) -> SessionAdminOut:
    session = await _load(db, session_id)
    await session_admin.publish_session(db, session)
    await db.commit()
    await queue.enqueue("sync_session_meeting", str(session_id))
    return await _serialize(db, await _load(db, session_id))


@router.post("/sessions/{session_id}/reschedule", response_model=SessionAdminOut)
async def reschedule_session(
    session_id: uuid.UUID, payload: RescheduleIn, db: DbSession, _: Superuser
) -> SessionAdminOut:
    session = await _load(db, session_id)
    await session_admin.reschedule_session(
        db, session, starts_at=payload.starts_at, duration_minutes=payload.duration_minutes
    )
    await db.commit()
    await queue.enqueue("sync_session_meeting", str(session_id))
    return await _serialize(db, await _load(db, session_id))


@router.post("/sessions/{session_id}/cancel", response_model=SessionAdminOut)
async def cancel_session(
    session_id: uuid.UUID, payload: CancelIn, db: DbSession, _: Superuser
) -> SessionAdminOut:
    """Cancel and refund every booking, regardless of the usual cutoff."""
    session = await _load(db, session_id)
    await booking_service.cancel_session(db, session, reason=payload.reason)
    await db.commit()
    await queue.enqueue("remove_session_meeting", str(session_id))
    return await _serialize(db, await _load(db, session_id))


@router.post("/sessions/{session_id}/retry-meeting", response_model=Message)
async def retry_meeting(session_id: uuid.UUID, db: DbSession, _: Superuser) -> Message:
    """Re-run the Meet creation for a session whose meeting failed.

    This is the one thing in the system that depends on a third party and can
    fail quietly, so it gets an explicit button in the admin UI.
    """
    session = await _load(db, session_id)
    if session.meeting is not None:
        session.meeting.attempts = 0
        session.meeting.last_error = None
    await db.commit()
    await queue.enqueue("sync_session_meeting", str(session_id))
    return Message(detail="Retrying — refresh in a few seconds.")


@router.get("/sessions/{session_id}/roster")
async def session_roster(session_id: uuid.UUID, db: DbSession, _: Superuser) -> dict:
    await _load(db, session_id)
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
                "name": b.learner.full_name,
                "email": b.learner.email,
                "level": b.learner.level.value if b.learner.level else None,
                "first_joined_at": b.first_joined_at,
                "attendance_confirmed_at": b.attendance_confirmed_at,
            }
            for b in bookings
            if b.status != BookingStatus.WAITLISTED
        ],
        "waitlist": [
            {
                "booking_id": str(b.id),
                "name": b.learner.full_name,
                "position": b.waitlist_position,
            }
            for b in bookings
            if b.status == BookingStatus.WAITLISTED
        ],
    }


@router.post("/bookings/{booking_id}/attendance", response_model=Message)
async def mark_attendance(
    booking_id: uuid.UUID, db: DbSession, _: Superuser, attended: Annotated[bool, Query()] = True
) -> Message:
    """Instructor-confirmed attendance.

    `conferenceRecords` is Workspace-only, so join-clicks are the automatic
    signal and this is the authoritative correction.
    """
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise NotFound("Booking not found.")
    booking.status = BookingStatus.ATTENDED if attended else BookingStatus.NO_SHOW
    booking.attendance_confirmed_at = utc_now()
    return Message(detail="Attendance recorded.")


@router.get("/instructors")
async def list_instructors_admin(db: DbSession, _: Superuser) -> list[dict]:
    """Includes Google connection status — an instructor who hasn't connected
    can't host, so the session form must be able to grey them out."""
    result = await db.execute(
        select(User, GoogleCredential)
        .outerjoin(GoogleCredential, GoogleCredential.user_id == User.id)
        .where(User.role.in_([UserRole.INSTRUCTOR, UserRole.SUPERUSER]))
        .order_by(User.full_name)
    )
    return [
        {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
            "google_connected": credential is not None and credential.revoked_at is None,
            "google_email": credential.google_email if credential else None,
        }
        for user, credential in result.all()
    ]

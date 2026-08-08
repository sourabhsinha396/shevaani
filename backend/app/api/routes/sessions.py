from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.api.serializers import serialize_sessions
from app.core.config import settings
from app.models.booking import Booking, JoinAccessLog
from app.models.enums import (
    BookingStatus,
    CEFRLevel,
    SessionKind,
    SessionStatus,
    UserRole,
)
from app.models.session import Session
from app.schemas.booking import BookingOut
from app.schemas.session import JoinOut, SessionOut
from app.services import booking as booking_service
from app.services.errors import MeetingNotReady, NotFound, OutsideJoinWindow, PermissionDenied
from app.services.scheduling import utc_now

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: DbSession,
    user: OptionalUser,
    kind: Annotated[SessionKind, Query()] = SessionKind.GROUP,
    level: Annotated[CEFRLevel | None, Query()] = None,
    starts_after: Annotated[datetime | None, Query()] = None,
    starts_before: Annotated[datetime | None, Query()] = None,
    include_full: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SessionOut]:
    """Public catalogue. Only published, not-yet-started sessions."""
    conditions = [
        Session.kind == kind,
        Session.status == SessionStatus.PUBLISHED,
        Session.starts_at > (starts_after or utc_now()),
    ]
    if starts_before is not None:
        conditions.append(Session.starts_at < starts_before)
    if level is not None:
        # Show sessions whose band contains the requested level.
        conditions.append(Session.level_min <= level)
        conditions.append(Session.level_max >= level)

    result = await db.execute(
        select(Session)
        .options(selectinload(Session.instructor))
        .where(*conditions)
        .order_by(Session.starts_at)
        .limit(limit)
        .offset(offset)
    )
    sessions = list(result.scalars().all())
    out = await serialize_sessions(db, sessions, learner_id=user.id if user else None)
    if not include_full:
        out = [s for s in out if not s.is_full]
    return out


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, db: DbSession, user: OptionalUser) -> SessionOut:
    result = await db.execute(
        select(Session).options(selectinload(Session.instructor)).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFound("Session not found.")

    out = await serialize_sessions(db, [session], learner_id=user.id if user else None)
    return out[0]


@router.post("/{session_id}/book", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def book_session(
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    allow_waitlist: Annotated[bool, Query()] = True,
) -> BookingOut:
    """Book a seat in a group discussion.

    Credits are pre-purchased, so a booking that clears the credit check is
    confirmed immediately — no payment round-trip here.
    """
    booking = await booking_service.book_group_session(
        db, session_id, user, allow_waitlist=allow_waitlist
    )
    return BookingOut.model_validate(booking)


@router.get("/{session_id}/join", response_model=JoinOut)
async def join_session(
    session_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> JoinOut:
    """Serve the Meet link.

    The join URL is a bearer credential — anyone holding it can attempt to join —
    so it lives behind this one endpoint, gated on an active booking and the time
    window, and every hit is logged.

    The decision is resolved *before* anything is raised, because raising unwinds
    through the `get_db` dependency and rolls the transaction back. Denials are
    the rows worth having — they are how you spot someone probing for links — so
    the audit row is committed first and the error raised afterwards.
    """
    result = await db.execute(
        select(Session).options(selectinload(Session.meeting)).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFound("Session not found.")

    now = utc_now()
    is_host = user.id == session.instructor_id or user.role == UserRole.SUPERUSER
    window_opens = session.starts_at - timedelta(minutes=settings.join_window_before_minutes)
    window_closes = session.ends_at + timedelta(minutes=settings.join_window_after_minutes)
    meeting = session.meeting

    booking: Booking | None = None
    if not is_host:
        booking_result = await db.execute(
            select(Booking).where(
                Booking.session_id == session.id,
                Booking.learner_id == user.id,
                Booking.status.in_(
                    [BookingStatus.CONFIRMED, BookingStatus.ATTENDED, BookingStatus.NO_SHOW]
                ),
            )
        )
        booking = booking_result.scalars().first()

    # Resolve the outcome without raising.
    denial: tuple[str, Exception] | None = None
    if not is_host and booking is None:
        denial = (
            "not_enrolled",
            PermissionDenied("You don't have a confirmed booking for this session."),
        )
    elif session.status == SessionStatus.CANCELLED:
        denial = ("session_cancelled", OutsideJoinWindow("This session was cancelled."))
    elif now < window_opens:
        denial = (
            "too_early",
            OutsideJoinWindow(
                f"The room opens {settings.join_window_before_minutes} minutes "
                f"before the session."
            ),
        )
    elif now > window_closes:
        denial = ("too_late", OutsideJoinWindow("This session has finished."))
    elif meeting is None or not meeting.is_ready:
        denial = (
            "meeting_not_ready",
            MeetingNotReady("The meeting link isn't ready yet. Try again in a moment."),
        )

    db.add(
        JoinAccessLog(
            session_id=session.id,
            user_id=user.id,
            booking_id=booking.id if booking else None,
            accessed_at=now,
            granted=denial is None,
            denial_reason=denial[0] if denial else None,
            ip_address=request.client.host if request.client else None,
        )
    )

    # First successful fetch is the automatic attendance signal. The instructor
    # confirms afterwards; conferenceRecords isn't available on consumer Gmail.
    if denial is None and booking is not None and booking.first_joined_at is None:
        booking.first_joined_at = now

    await db.commit()

    if denial is not None:
        raise denial[1]

    return JoinOut(
        join_url=meeting.join_url or "" if meeting else "",
        session_id=session.id,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
    )

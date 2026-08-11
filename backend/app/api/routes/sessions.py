from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.api.ratelimit import limiter
from app.api.serializers import serialize_sessions
from app.core.config import settings
from app.core.ratelimit import BOOKING, JOIN, JOIN_PER_IP
from app.models.booking import Booking, JoinAccessLog
from app.models.enums import (
    BookingStatus,
    SessionStatus,
    UserRole,
)
from app.models.session import OneOnOneSession, Session
from app.schemas.booking import BookingOut
from app.schemas.session import JoinOut, SessionOut
from app.services import booking as booking_service
from app.services.errors import MeetingNotReady, NotFound, OutsideJoinWindow, PermissionDenied
from app.services.scheduling import utc_now

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _group_ref_clause(ref: str):
    """WHERE clause matching a group session by UUID or slug. A slug can never
    parse as a UUID, so the two namespaces cannot collide."""
    parsed = _parse_uuid(ref)
    return Session.id == parsed if parsed is not None else Session.slug == ref


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    db: DbSession,
    user: OptionalUser,
    starts_after: Annotated[datetime | None, Query()] = None,
    starts_before: Annotated[datetime | None, Query()] = None,
    include_full: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SessionOut]:
    """Public catalogue of group discussions. Only published, not-yet-started.

    The ``kind`` filter is gone with the column since 0009 — this table holds
    nothing but group discussions now, and a one-to-one is never in a catalogue
    to begin with: it does not exist until somebody books the hour.
    """
    conditions = [
        Session.status == SessionStatus.PUBLISHED,
        Session.starts_at > (starts_after or utc_now()),
    ]
    if starts_before is not None:
        conditions.append(Session.starts_at < starts_before)

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
async def get_session(session_id: str, db: DbSession, user: OptionalUser) -> SessionOut:
    """By UUID or by slug — the catalogue links by slug now, but every id ever
    shared keeps working."""
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.instructor))
        .where(_group_ref_clause(session_id))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFound("Session not found.")

    out = await serialize_sessions(db, [session], learner_id=user.id if user else None)
    return out[0]


@router.post(
    "/{session_id}/book",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limiter("book", BOOKING))],
)
async def book_session(
    session_id: str,
    db: DbSession,
    user: CurrentUser,
    allow_waitlist: Annotated[bool, Query()] = True,
) -> BookingOut:
    """Book a seat in a group discussion.

    Credits are pre-purchased, so a booking that clears the credit check is
    confirmed immediately — no payment round-trip here.
    """
    resolved = (
        await db.execute(select(Session.id).where(_group_ref_clause(session_id)))
    ).scalar_one_or_none()
    if resolved is None:
        raise NotFound("Session not found.")
    booking = await booking_service.book_group_session(
        db, resolved, user, allow_waitlist=allow_waitlist
    )
    return BookingOut.model_validate(booking)


@router.get(
    "/{session_id}/join",
    response_model=JoinOut,
    # Two buckets. The per-user one is the real limit; the per-IP one is what
    # stops someone with a handful of accounts spreading enumeration across them
    # and staying under it.
    dependencies=[Depends(limiter("join", JOIN, per_ip=JOIN_PER_IP))],
)
async def join_session(
    session_id: str,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> JoinOut:
    """Serve the Meet link, and record that somebody walked through the door.

    The link itself is also on ``GET /bookings`` now — a Meet room admits nobody
    before its host arrives, so a link seen early is a lobby and not a way in.
    What this endpoint still owns is the *event*: it is called when a learner
    actually goes to join, which is what makes the audit trail and the automatic
    attendance signal mean anything. Fetching a page is not attending; clicking
    join is at least a claim to have tried.

    ``session_id`` may name either kind of session. A booking is what grants
    access whichever table it lands in, and making a client know which endpoint
    to call would only be asking it to re-derive something it was already told.

    The decision is resolved *before* anything is raised, because raising unwinds
    through the `get_db` dependency and rolls the transaction back. Denials are
    the rows worth having — they are how you spot someone probing for links — so
    the audit row is committed first and the error raised afterwards.
    """
    session = await _load_joinable(db, session_id)
    if session is None:
        raise NotFound("Session not found.")

    is_group = isinstance(session, Session)
    now = utc_now()
    is_host = user.id == session.instructor_id or user.role == UserRole.SUPERUSER
    window_opens = session.starts_at - timedelta(minutes=settings.join_window_before_minutes)
    window_closes = session.ends_at + timedelta(minutes=settings.join_window_after_minutes)
    meeting = session.meeting

    booking: Booking | None = None
    if not is_host:
        parent_column = Booking.session_id if is_group else Booking.one_on_one_id
        booking_result = await db.execute(
            select(Booking).where(
                parent_column == session.id,
                Booking.learner_id == user.id,
                Booking.status.in_(
                    [BookingStatus.CONFIRMED, BookingStatus.ATTENDED, BookingStatus.NO_SHOW]
                ),
            )
        )
        booking = booking_result.scalars().first()

    # Resolve the outcome without raising. There is no "too early" any more —
    # the room is its own gate before the hour.
    denial: tuple[str, Exception] | None = None
    if not is_host and booking is None:
        denial = (
            "not_enrolled",
            PermissionDenied("You don't have a confirmed booking for this session."),
        )
    elif session.status == SessionStatus.CANCELLED:
        denial = ("session_cancelled", OutsideJoinWindow("This session was cancelled."))
    elif now > window_closes:
        denial = ("too_late", OutsideJoinWindow("This session has finished."))
    elif meeting is None or not meeting.is_ready:
        denial = (
            "meeting_not_ready",
            MeetingNotReady("The meeting link isn't ready yet. Try again in a moment."),
        )

    db.add(
        JoinAccessLog(
            session_id=session.id if is_group else None,
            one_on_one_id=None if is_group else session.id,
            user_id=user.id,
            booking_id=booking.id if booking else None,
            accessed_at=now,
            granted=denial is None,
            denial_reason=denial[0] if denial else None,
            ip_address=request.client.host if request.client else None,
        )
    )

    # First fetch *within the window* is the automatic attendance signal. The
    # window matters here even though it no longer gates the link: someone
    # opening the room the evening before has not attended anything, and
    # recording that they had would quietly make the roster wrong. The
    # instructor confirms afterwards either way — conferenceRecords isn't
    # available on consumer Gmail.
    if (
        denial is None
        and booking is not None
        and booking.first_joined_at is None
        and now >= window_opens
    ):
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


async def _load_joinable(
    db: AsyncSession, ref: str
) -> Session | OneOnOneSession | None:
    """Whichever table holds this id (or slug), with its meeting loaded. Ids
    are UUIDs from two sequences that never collide, so trying one and then
    the other is unambiguous; a slug only ever names a group session."""
    group = await db.execute(
        select(Session).options(selectinload(Session.meeting)).where(_group_ref_clause(ref))
    )
    session = group.scalar_one_or_none()
    if session is not None:
        return session

    parsed = _parse_uuid(ref)
    if parsed is None:
        return None
    one_on_one = await db.execute(
        select(OneOnOneSession)
        .options(selectinload(OneOnOneSession.meeting))
        .where(OneOnOneSession.id == parsed)
    )
    return one_on_one.scalar_one_or_none()

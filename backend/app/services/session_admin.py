"""Superuser-facing session management, and instructor time blocking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.availability import InstructorBlock
from app.models.booking import Booking
from app.models.enums import (
    SEAT_HOLDING_STATUSES,
    BlockReason,
    BookingStatus,
    CEFRLevel,
    SessionKind,
    SessionStatus,
    UserRole,
)
from app.models.session import Session, SessionMeeting
from app.models.user import User
from app.services import booking as booking_service
from app.services import scheduling
from app.services.errors import Conflict, DomainError, NotFound, PermissionDenied, SchedulingError
from app.services.scheduling import utc_now


async def _load_instructor(db: AsyncSession, instructor_id: uuid.UUID) -> User:
    instructor = await db.get(User, instructor_id)
    if instructor is None or not instructor.is_active:
        raise NotFound("Instructor not found.")
    if instructor.role not in (UserRole.INSTRUCTOR, UserRole.SUPERUSER):
        raise DomainError("That user is not an instructor.")
    return instructor


async def create_group_session(
    db: AsyncSession,
    *,
    created_by: User,
    instructor_id: uuid.UUID,
    title: str,
    starts_at: datetime,
    duration_minutes: int,
    min_seats: int,
    max_seats: int,
    price_credits: int,
    level_min: CEFRLevel,
    level_max: CEFRLevel,
    topic: str | None = None,
    description: str | None = None,
    prep_material_url: str | None = None,
    publish: bool = False,
) -> Session:
    instructor = await _load_instructor(db, instructor_id)

    # An instructor without a connected Google account cannot host — the Meet
    # link is created on *their* calendar. Fail here, loudly, rather than let a
    # session sit with a broken meeting two days before it runs.
    await db.refresh(instructor, ["google_credential"])
    if publish and not instructor.can_host:
        raise Conflict(
            f"{instructor.full_name} hasn't connected a Google account yet, "
            f"so no Meet link can be created. Ask them to connect it, or save this as a draft."
        )

    if level_min.rank > level_max.rank:
        raise DomainError("The minimum level cannot be above the maximum level.")

    ends_at = starts_at + timedelta(minutes=duration_minutes)

    await scheduling.lock_instructor(db, instructor_id)
    await scheduling.assert_instructor_available(
        db, instructor_id, starts_at, ends_at, kind=SessionKind.GROUP
    )

    session = Session(
        kind=SessionKind.GROUP,
        status=SessionStatus.PUBLISHED if publish else SessionStatus.DRAFT,
        title=title,
        topic=topic,
        description=description,
        prep_material_url=prep_material_url,
        level_min=level_min,
        level_max=level_max,
        starts_at=starts_at,
        ends_at=ends_at,
        min_seats=min_seats,
        max_seats=max_seats,
        price_credits=price_credits,
        instructor_id=instructor_id,
        created_by_id=created_by.id,
    )
    db.add(session)
    db.add(SessionMeeting(session=session))

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SchedulingError("That slot conflicts with another session.") from exc

    return session


async def update_group_session(
    db: AsyncSession,
    session: Session,
    *,
    title: str | None = None,
    topic: str | None = None,
    description: str | None = None,
    prep_material_url: str | None = None,
    level_min: CEFRLevel | None = None,
    level_max: CEFRLevel | None = None,
    min_seats: int | None = None,
    max_seats: int | None = None,
    price_credits: int | None = None,
) -> Session:
    """Editable content. Rescheduling and re-assigning go through their own paths
    because both have side effects beyond the row."""
    if session.status == SessionStatus.CANCELLED:
        raise Conflict("This session is cancelled.")

    if max_seats is not None:
        taken = await booking_service.seats_taken(db, session.id)
        if max_seats < taken:
            raise Conflict(
                f"{taken} learner(s) are already booked — capacity cannot go below that."
            )
        session.max_seats = max_seats
    if min_seats is not None:
        session.min_seats = min_seats
    if session.min_seats > session.max_seats:
        raise DomainError("Minimum seats cannot exceed maximum seats.")

    if title is not None:
        session.title = title
    if topic is not None:
        session.topic = topic
    if description is not None:
        session.description = description
    if prep_material_url is not None:
        session.prep_material_url = prep_material_url
    if level_min is not None:
        session.level_min = level_min
    if level_max is not None:
        session.level_max = level_max
    if session.level_min.rank > session.level_max.rank:
        raise DomainError("The minimum level cannot be above the maximum level.")

    if price_credits is not None:
        # Changing the price does not retro-charge or retro-refund existing bookings.
        session.price_credits = price_credits

    await db.flush()
    return session


async def reschedule_session(
    db: AsyncSession,
    session: Session,
    *,
    starts_at: datetime,
    duration_minutes: int | None = None,
) -> Session:
    """Move a session, keeping the denormalised booking times in step.

    This is the one place the ``bookings.starts_at``/``ends_at`` invariant can be
    broken, so it is the one place that must update them — in the same
    transaction, before the learner-overlap constraint is re-checked at commit.
    """
    if session.status == SessionStatus.CANCELLED:
        raise Conflict("This session is cancelled.")

    duration = timedelta(
        minutes=duration_minutes
        or int((session.ends_at - session.starts_at).total_seconds() // 60)
    )
    ends_at = starts_at + duration

    await scheduling.lock_instructor(db, session.instructor_id)
    await scheduling.assert_instructor_available(
        db,
        session.instructor_id,
        starts_at,
        ends_at,
        kind=session.kind,
        exclude_session_id=session.id,
    )

    session.starts_at = starts_at
    session.ends_at = ends_at

    result = await db.execute(
        select(Booking).where(
            Booking.session_id == session.id,
            Booking.status.in_([*SEAT_HOLDING_STATUSES, BookingStatus.WAITLISTED]),
        )
    )
    for bk in result.scalars().all():
        bk.starts_at = starts_at
        bk.ends_at = ends_at

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict(
            "Rescheduling would clash with another session for one of the booked learners."
        ) from exc

    # The Calendar event has to move too — the caller enqueues sync_session_meeting
    # after committing.
    return session


async def publish_session(db: AsyncSession, session: Session) -> Session:
    if session.status == SessionStatus.CANCELLED:
        raise Conflict("This session is cancelled.")

    instructor = await db.get(User, session.instructor_id)
    if instructor is not None:
        await db.refresh(instructor, ["google_credential"])
        if not instructor.can_host:
            raise Conflict(
                f"{instructor.full_name} hasn't connected a Google account, "
                f"so this session can't get a Meet link."
            )

    session.status = SessionStatus.PUBLISHED
    await db.flush()
    return session


@dataclass(frozen=True)
class AutoCancellation:
    """What the sweep did to one session.

    The counts are captured *before* the cancellation, because afterwards there
    is nothing left to count — every booking is CANCELLED and ``seats_taken``
    honestly returns zero. Anything reporting on this run (the worker log, the
    Slack line) needs the before picture.
    """

    session: Session
    seats_taken: int
    learners_affected: int


async def auto_cancel_underfilled(
    db: AsyncSession, *, now: datetime | None = None
) -> list[AutoCancellation]:
    """Cancel group sessions that won't reach ``min_seats`` in time, and refund.

    Without this you either run one-person "group discussions" or cancel them by
    hand at 6am.
    """
    now = now or utc_now()
    horizon = now + timedelta(hours=settings.group_autocancel_hours_before)

    result = await db.execute(
        select(Session).where(
            Session.kind == SessionKind.GROUP,
            Session.status == SessionStatus.PUBLISHED,
            Session.starts_at > now,
            Session.starts_at <= horizon,
        )
    )
    cancelled: list[AutoCancellation] = []
    for session in result.scalars().all():
        taken = await booking_service.seats_taken(db, session.id)
        if taken >= session.min_seats:
            continue
        affected = await booking_service.cancel_session(
            db,
            session,
            reason=f"Not enough learners joined ({taken} of {session.min_seats} needed).",
            automatic=True,
        )
        cancelled.append(
            AutoCancellation(
                session=session, seats_taken=taken, learners_affected=len(affected)
            )
        )
    return cancelled


# --------------------------------------------------------------- time blocking


async def create_block(
    db: AsyncSession,
    *,
    instructor: User,
    actor: User,
    starts_at: datetime,
    ends_at: datetime,
    reason: BlockReason = BlockReason.BUSY,
    note: str | None = None,
) -> InstructorBlock:
    """Mark an instructor unavailable.

    Refuses if live sessions already sit in the range. Silently cancelling
    someone's booked class as a side effect of "I'm busy Tuesday" would be the
    wrong default — the caller is told what's in the way and decides.
    """
    if actor.id != instructor.id and actor.role != UserRole.SUPERUSER:
        raise PermissionDenied("You can only block your own calendar.")
    if ends_at <= starts_at:
        raise DomainError("The block must end after it starts.")

    await scheduling.lock_instructor(db, instructor.id)

    clashes = await scheduling.find_sessions_overlapping(db, instructor.id, starts_at, ends_at)
    if clashes:
        listed = ", ".join(
            f"'{s.title}' at {s.starts_at.astimezone(settings.tz):%d %b %H:%M}" for s in clashes[:3]
        )
        raise Conflict(
            f"{len(clashes)} session(s) are already scheduled in that range ({listed}). "
            f"Cancel or move them first."
        )

    block = InstructorBlock(
        instructor_id=instructor.id,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        note=note,
        created_by_id=actor.id,
    )
    db.add(block)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("That overlaps a block you've already set.") from exc

    return block


async def delete_block(db: AsyncSession, block: InstructorBlock, actor: User) -> None:
    if actor.id != block.instructor_id and actor.role != UserRole.SUPERUSER:
        raise PermissionDenied("You can only unblock your own calendar.")
    await db.delete(block)
    await db.flush()


async def list_blocks(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[InstructorBlock]:
    conditions = [InstructorBlock.instructor_id == instructor_id]
    if since is not None:
        conditions.append(InstructorBlock.ends_at > since)
    if until is not None:
        conditions.append(InstructorBlock.starts_at < until)

    result = await db.execute(
        select(InstructorBlock).where(*conditions).order_by(InstructorBlock.starts_at)
    )
    return list(result.scalars().all())

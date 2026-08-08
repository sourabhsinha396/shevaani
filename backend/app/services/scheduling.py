"""One-to-one scheduling rules.

Two rules govern one-to-one bookings, both configurable:

1. The whole session must sit inside 07:00-19:00 in ``BOOKING_TIMEZONE`` (IST).
2. A one-to-one keeps ``ONE_ON_ONE_BUFFER_MINUTES`` clear either side of it.

Plus instructor blocks, which are hard and win over everything.

The database enforces overlap and the 1:1-vs-1:1 buffer (see migration 0001).
This module enforces the parts an exclusion constraint cannot express — the
booking window, blocks, and the buffer between a 1:1 and an adjacent *group*
session — and it does so under an instructor row lock so concurrent attempts
serialise.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.availability import InstructorBlock
from app.models.enums import SessionKind, SessionStatus
from app.models.session import Session
from app.models.user import User
from app.services.errors import SchedulingError


@dataclass(frozen=True)
class Slot:
    starts_at: datetime
    ends_at: datetime


def _buffer() -> timedelta:
    return timedelta(minutes=settings.one_on_one_buffer_minutes)


async def lock_instructor(db: AsyncSession, instructor_id: uuid.UUID) -> None:
    """Serialise every scheduling decision for one instructor.

    Cheap (one row), and it closes the window between "we checked nothing
    conflicts" and "we inserted". Take this before any of the checks below.
    """
    await db.execute(select(User.id).where(User.id == instructor_id).with_for_update())


def validate_booking_window(starts_at: datetime, ends_at: datetime) -> None:
    """The whole session must fall inside the local booking window on one local day."""
    local_start = starts_at.astimezone(settings.tz)
    local_end = ends_at.astimezone(settings.tz)

    if local_start.date() != local_end.date():
        raise SchedulingError(
            f"A one-to-one session must start and end on the same day in "
            f"{settings.booking_timezone}."
        )

    window_start = settings.one_on_one_window_start
    window_end = settings.one_on_one_window_end

    if local_start.time() < window_start or local_end.time() > window_end:
        raise SchedulingError(
            f"One-to-one sessions can only be booked between "
            f"{window_start:%H:%M} and {window_end:%H:%M} "
            f"{settings.booking_timezone}. "
            f"Requested {local_start:%H:%M}-{local_end:%H:%M}."
        )


async def find_blocking_block(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> InstructorBlock | None:
    result = await db.execute(
        select(InstructorBlock).where(
            InstructorBlock.instructor_id == instructor_id,
            InstructorBlock.starts_at < ends_at,
            InstructorBlock.ends_at > starts_at,
        )
    )
    return result.scalars().first()


async def find_conflicting_session(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    *,
    apply_buffer: bool,
    exclude_session_id: uuid.UUID | None = None,
) -> Session | None:
    """The instructor's first session clashing with [starts_at, ends_at).

    With ``apply_buffer`` the requested range is widened by the configured buffer
    on both sides, so an adjacent session inside the buffer counts as a clash.
    """
    lo, hi = starts_at, ends_at
    if apply_buffer:
        lo -= _buffer()
        hi += _buffer()

    conditions = [
        Session.instructor_id == instructor_id,
        Session.status != SessionStatus.CANCELLED,
        Session.starts_at < hi,
        Session.ends_at > lo,
    ]
    if exclude_session_id is not None:
        conditions.append(Session.id != exclude_session_id)

    result = await db.execute(select(Session).where(and_(*conditions)).order_by(Session.starts_at))
    return result.scalars().first()


async def assert_instructor_available(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    *,
    kind: SessionKind,
    exclude_session_id: uuid.UUID | None = None,
) -> None:
    """Full pre-insert check. Call ``lock_instructor`` first."""
    if kind == SessionKind.ONE_ON_ONE:
        validate_booking_window(starts_at, ends_at)

    block = await find_blocking_block(db, instructor_id, starts_at, ends_at)
    if block is not None:
        local = block.starts_at.astimezone(settings.tz)
        raise SchedulingError(
            f"The instructor has blocked this time "
            f"({local:%d %b %H:%M} onwards, {block.reason.value})."
        )

    clash = await find_conflicting_session(
        db,
        instructor_id,
        starts_at,
        ends_at,
        # A one-to-one needs its buffer respected against anything adjacent.
        apply_buffer=kind == SessionKind.ONE_ON_ONE,
        exclude_session_id=exclude_session_id,
    )
    if clash is not None:
        raise SchedulingError(
            f"Conflicts with '{clash.title}' at "
            f"{clash.starts_at.astimezone(settings.tz):%d %b %H:%M}."
        )

    # A group session must also stay clear of the buffer around existing 1:1s.
    if kind == SessionKind.GROUP:
        neighbour = await _find_one_on_one_within_buffer(
            db, instructor_id, starts_at, ends_at, exclude_session_id
        )
        if neighbour is not None:
            raise SchedulingError(
                f"Too close to a one-to-one at "
                f"{neighbour.starts_at.astimezone(settings.tz):%d %b %H:%M} — "
                f"{settings.one_on_one_buffer_minutes} minutes must be kept clear."
            )


async def _find_one_on_one_within_buffer(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_session_id: uuid.UUID | None,
) -> Session | None:
    buffer = _buffer()
    conditions = [
        Session.instructor_id == instructor_id,
        Session.kind == SessionKind.ONE_ON_ONE,
        Session.status != SessionStatus.CANCELLED,
        Session.starts_at - buffer < ends_at,
        Session.ends_at + buffer > starts_at,
    ]
    if exclude_session_id is not None:
        conditions.append(Session.id != exclude_session_id)

    result = await db.execute(select(Session).where(and_(*conditions)))
    return result.scalars().first()


async def available_slots(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    on_date: date,
    *,
    duration_minutes: int | None = None,
    now: datetime | None = None,
) -> list[Slot]:
    """Bookable one-to-one slots for an instructor on a local calendar date.

    Walks the booking window in ``ONE_ON_ONE_SLOT_MINUTES`` steps and drops any
    candidate that is in the past, inside a block, or within the buffer of an
    existing session. One query for sessions, one for blocks — the filtering is
    done in Python because the candidate set is a dozen slots at most.
    """
    now = now or datetime.now(UTC)
    duration = timedelta(minutes=duration_minutes or settings.one_on_one_slot_minutes)
    step = timedelta(minutes=settings.one_on_one_slot_minutes)
    buffer = _buffer()

    day_start = datetime.combine(on_date, settings.one_on_one_window_start, tzinfo=settings.tz)
    day_end = datetime.combine(on_date, settings.one_on_one_window_end, tzinfo=settings.tz)

    # Widen the fetch by the buffer so neighbours just outside the day still count.
    fetch_lo = day_start - buffer - timedelta(hours=6)
    fetch_hi = day_end + buffer + timedelta(hours=6)

    sessions = (
        (
            await db.execute(
                select(Session).where(
                    Session.instructor_id == instructor_id,
                    Session.status != SessionStatus.CANCELLED,
                    Session.starts_at < fetch_hi,
                    Session.ends_at > fetch_lo,
                )
            )
        )
        .scalars()
        .all()
    )
    blocks = (
        (
            await db.execute(
                select(InstructorBlock).where(
                    InstructorBlock.instructor_id == instructor_id,
                    InstructorBlock.starts_at < fetch_hi,
                    InstructorBlock.ends_at > fetch_lo,
                )
            )
        )
        .scalars()
        .all()
    )

    slots: list[Slot] = []
    cursor = day_start
    while cursor + duration <= day_end:
        slot_start, slot_end = cursor, cursor + duration
        cursor += step

        if slot_start <= now:
            continue
        if any(b.starts_at < slot_end and b.ends_at > slot_start for b in blocks):
            continue
        # Every existing session must sit at least `buffer` away from this slot.
        if any(
            s.starts_at < slot_end + buffer and s.ends_at > slot_start - buffer for s in sessions
        ):
            continue

        slots.append(Slot(starts_at=slot_start, ends_at=slot_end))

    return slots


async def find_sessions_overlapping(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> list[Session]:
    """Live sessions in a range — used to refuse a block that would strand learners."""
    result = await db.execute(
        select(Session)
        .where(
            Session.instructor_id == instructor_id,
            Session.status.in_([SessionStatus.DRAFT, SessionStatus.PUBLISHED]),
            Session.starts_at < ends_at,
            Session.ends_at > starts_at,
        )
        .order_by(Session.starts_at)
    )
    return list(result.scalars().all())


def utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "Slot",
    "assert_instructor_available",
    "available_slots",
    "find_blocking_block",
    "find_conflicting_session",
    "find_sessions_overlapping",
    "lock_instructor",
    "utc_now",
    "validate_booking_window",
]

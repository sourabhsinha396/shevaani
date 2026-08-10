"""One-to-one scheduling rules.

Two rules govern one-to-one bookings, both configurable:

1. The whole session must sit inside 07:00-19:00 in ``BOOKING_TIMEZONE`` (IST).
2. A one-to-one keeps ``ONE_ON_ONE_BUFFER_MINUTES`` clear either side of it.

Plus instructor blocks, which are hard and win over everything.

The database enforces overlap — through `instructor_engagements`, which mirrors
both session tables and carries the exclusion constraint — and the 1:1-vs-1:1
buffer. See migrations 0001 and 0009. This module enforces the parts an
exclusion constraint cannot express: the booking window, blocks, and the buffer
between a 1:1 and an adjacent *group* session. It does so under an instructor
row lock so concurrent attempts serialise.

"Is this instructor free?" is therefore a question about `instructor_engagements`
and never about `sessions` — that table only holds half the answer.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.availability import InstructorBlock
from app.models.enums import SessionStatus, UserRole
from app.models.session import InstructorEngagement, OneOnOneSession, Session
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


async def find_conflicting_engagement(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    *,
    apply_buffer: bool,
    exclude_source_id: uuid.UUID | None = None,
) -> InstructorEngagement | None:
    """The instructor's first commitment clashing with [starts_at, ends_at).

    Reads ``instructor_engagements`` rather than the session tables: since 0009
    a session's hour can come from either of two tables, and this is the one
    place that holds both. Cancelled rows are absent by construction — the
    trigger deletes the engagement — so there is no status filter here.

    With ``apply_buffer`` the requested range is widened by the configured
    buffer on both sides, so an adjacent commitment inside the buffer counts.
    """
    lo, hi = starts_at, ends_at
    if apply_buffer:
        lo -= _buffer()
        hi += _buffer()

    conditions = [
        InstructorEngagement.instructor_id == instructor_id,
        InstructorEngagement.starts_at < hi,
        InstructorEngagement.ends_at > lo,
    ]
    if exclude_source_id is not None:
        conditions.append(InstructorEngagement.source_id != exclude_source_id)

    result = await db.execute(
        select(InstructorEngagement)
        .where(and_(*conditions))
        .order_by(InstructorEngagement.starts_at)
    )
    return result.scalars().first()


async def assert_instructor_available(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
    *,
    one_on_one: bool,
    exclude_source_id: uuid.UUID | None = None,
) -> None:
    """Full pre-insert check. Call ``lock_instructor`` first."""
    if one_on_one:
        validate_booking_window(starts_at, ends_at)

    block = await find_blocking_block(db, instructor_id, starts_at, ends_at)
    if block is not None:
        local = block.starts_at.astimezone(settings.tz)
        raise SchedulingError(
            f"The instructor has blocked this time "
            f"({local:%d %b %H:%M} onwards, {block.reason.value})."
        )

    clash = await find_conflicting_engagement(
        db,
        instructor_id,
        starts_at,
        ends_at,
        # A one-to-one needs its buffer respected against anything adjacent.
        apply_buffer=one_on_one,
        exclude_source_id=exclude_source_id,
    )
    if clash is not None:
        raise SchedulingError(
            f"Conflicts with another session at "
            f"{clash.starts_at.astimezone(settings.tz):%d %b %H:%M}."
        )

    # A group session must also stay clear of the buffer around existing 1:1s.
    # This is the case an exclusion constraint still cannot express — it filters
    # rows, not pairs — so it stays here, under the instructor row lock.
    if not one_on_one:
        neighbour = await _find_one_on_one_within_buffer(
            db, instructor_id, starts_at, ends_at, exclude_source_id
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
    exclude_source_id: uuid.UUID | None,
) -> InstructorEngagement | None:
    buffer = _buffer()
    conditions = [
        InstructorEngagement.instructor_id == instructor_id,
        InstructorEngagement.source == InstructorEngagement.ONE_ON_ONE,
        InstructorEngagement.starts_at - buffer < ends_at,
        InstructorEngagement.ends_at + buffer > starts_at,
    ]
    if exclude_source_id is not None:
        conditions.append(InstructorEngagement.source_id != exclude_source_id)

    result = await db.execute(select(InstructorEngagement).where(and_(*conditions)))
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
    existing commitment. One query for engagements, one for blocks — the
    filtering is done in Python because the candidate set is a dozen slots.
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

    engagements = (
        (
            await db.execute(
                select(InstructorEngagement).where(
                    InstructorEngagement.instructor_id == instructor_id,
                    InstructorEngagement.starts_at < fetch_hi,
                    InstructorEngagement.ends_at > fetch_lo,
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
        # Every existing commitment must sit at least `buffer` away from this slot.
        if any(
            e.starts_at < slot_end + buffer and e.ends_at > slot_start - buffer
            for e in engagements
        ):
            continue

        slots.append(Slot(starts_at=slot_start, ends_at=slot_end))

    return slots


# --------------------------------------------- availability across the whole team
#
# The booking page never names an instructor — a learner is choosing an hour,
# not a person, and who teaches it is settled at booking time. So what the page
# needs is the *union* of everyone's free slots, and then somebody free to take
# the one that was picked. Both live here.


async def active_instructor_ids(db: AsyncSession) -> list[uuid.UUID]:
    result = await db.execute(
        select(User.id)
        .where(
            User.role.in_([UserRole.INSTRUCTOR, UserRole.SUPERUSER]),
            User.is_active.is_(True),
        )
        .order_by(User.id)
    )
    return list(result.scalars().all())


def _is_free(
    slot_start: datetime,
    slot_end: datetime,
    *,
    engagements: list[InstructorEngagement],
    blocks: list[InstructorBlock],
    buffer: timedelta,
) -> bool:
    if any(b.starts_at < slot_end and b.ends_at > slot_start for b in blocks):
        return False
    return not any(
        e.starts_at < slot_end + buffer and e.ends_at > slot_start - buffer for e in engagements
    )


async def _walk_open_slots(
    db: AsyncSession,
    start: date,
    end: date,
    *,
    duration_minutes: int | None = None,
    now: datetime | None = None,
) -> Iterator[tuple[date, datetime]]:
    """Every open slot in the range, in order, as ``(local date, start)`` pairs.

    Two queries for the entire range rather than two per instructor per day: a
    month across a handful of instructors is a few hundred rows, and walking
    them in Python is cheaper than the round trips.

    Returns a *lazy* iterator over the already-fetched rows so a caller that
    only wants to know whether anything is open at all can stop at the first
    hit instead of costing out the whole month. The two queries are paid either
    way; the loop is not.
    """
    now = now or datetime.now(UTC)
    if end < start:
        return iter(())
    instructor_ids = await active_instructor_ids(db)
    if not instructor_ids:
        return iter(())

    duration = timedelta(minutes=duration_minutes or settings.one_on_one_slot_minutes)
    step = timedelta(minutes=settings.one_on_one_slot_minutes)
    buffer = _buffer()

    window_start = settings.one_on_one_window_start
    window_end = settings.one_on_one_window_end
    # Widened like `available_slots` does, so neighbours sitting just outside the
    # range still push the slots at its edges out of reach.
    fetch_lo = datetime.combine(start, window_start, tzinfo=settings.tz) - buffer - timedelta(hours=6)
    fetch_hi = datetime.combine(end, window_end, tzinfo=settings.tz) + buffer + timedelta(hours=6)

    # One query across both kinds of session, which is the whole point of the
    # engagements table. Cancelled rows are absent by construction.
    engagements_by_instructor: dict[uuid.UUID, list[InstructorEngagement]] = defaultdict(list)
    for engagement in (
        (
            await db.execute(
                select(InstructorEngagement).where(
                    InstructorEngagement.instructor_id.in_(instructor_ids),
                    InstructorEngagement.starts_at < fetch_hi,
                    InstructorEngagement.ends_at > fetch_lo,
                )
            )
        )
        .scalars()
        .all()
    ):
        engagements_by_instructor[engagement.instructor_id].append(engagement)

    blocks_by_instructor: dict[uuid.UUID, list[InstructorBlock]] = defaultdict(list)
    for block in (
        (
            await db.execute(
                select(InstructorBlock).where(
                    InstructorBlock.instructor_id.in_(instructor_ids),
                    InstructorBlock.starts_at < fetch_hi,
                    InstructorBlock.ends_at > fetch_lo,
                )
            )
        )
        .scalars()
        .all()
    ):
        blocks_by_instructor[block.instructor_id].append(block)

    def walk() -> Iterator[tuple[date, datetime]]:
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            day_start = datetime.combine(day, window_start, tzinfo=settings.tz)
            day_end = datetime.combine(day, window_end, tzinfo=settings.tz)

            cursor = day_start
            while cursor + duration <= day_end:
                slot_start, slot_end = cursor, cursor + duration
                cursor += step

                if slot_start <= now:
                    continue
                if any(
                    _is_free(
                        slot_start,
                        slot_end,
                        engagements=engagements_by_instructor.get(i, []),
                        blocks=blocks_by_instructor.get(i, []),
                        buffer=buffer,
                    )
                    for i in instructor_ids
                ):
                    yield day, slot_start

    return walk()


async def open_slots(
    db: AsyncSession,
    start: date,
    end: date,
    *,
    duration_minutes: int | None = None,
    now: datetime | None = None,
) -> dict[date, list[datetime]]:
    """Slots at least one instructor could take, keyed by local calendar date.

    Days with nothing free are absent from the mapping rather than present and
    empty, which is what lets the calendar grey them out without a second
    request.
    """
    by_day: dict[date, list[datetime]] = defaultdict(list)
    for day, slot in await _walk_open_slots(
        db, start, end, duration_minutes=duration_minutes, now=now
    ):
        by_day[day].append(slot)
    return dict(by_day)


async def first_open_slot(
    db: AsyncSession,
    start: date,
    end: date,
    *,
    duration_minutes: int | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """The soonest bookable one-to-one start in the range, or ``None``.

    Exists so the site chrome can ask "is one-to-one bookable at all?" without
    costing out a month of slots on every page load. The answer is almost
    always yes and almost always found on the first day walked.
    """
    for _, slot in await _walk_open_slots(
        db, start, end, duration_minutes=duration_minutes, now=now
    ):
        return slot
    return None


async def instructors_free_at(
    db: AsyncSession, starts_at: datetime, ends_at: datetime
) -> list[uuid.UUID]:
    """Active instructors who could take this range — an *unlocked* prefilter.

    Narrows the field before a row lock is taken; it decides nothing. The
    authoritative check is still `assert_instructor_available` under
    `lock_instructor`, because anything read here can go stale in the microsecond
    after it is read.
    """
    free: list[uuid.UUID] = []
    for instructor_id in await active_instructor_ids(db):
        if await find_blocking_block(db, instructor_id, starts_at, ends_at) is not None:
            continue
        if (
            await find_conflicting_engagement(
                db, instructor_id, starts_at, ends_at, apply_buffer=True
            )
            is not None
        ):
            continue
        free.append(instructor_id)
    return free


async def find_sessions_overlapping(
    db: AsyncSession,
    instructor_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> list[Session | OneOnOneSession]:
    """Live sessions in a range — used to refuse a block that would strand learners.

    Both tables, not the engagements view: the caller names what it found, and
    an engagement row deliberately carries no title. Two small queries against
    an indexed range, merged in Python.
    """
    live = [SessionStatus.DRAFT, SessionStatus.PUBLISHED]
    found: list[Session | OneOnOneSession] = []
    for model in (Session, OneOnOneSession):
        result = await db.execute(
            select(model).where(
                model.instructor_id == instructor_id,
                model.status.in_(live),
                model.starts_at < ends_at,
                model.ends_at > starts_at,
            )
        )
        found.extend(result.scalars().all())
    return sorted(found, key=lambda s: s.starts_at)


def utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "Slot",
    "active_instructor_ids",
    "assert_instructor_available",
    "available_slots",
    "find_blocking_block",
    "find_conflicting_engagement",
    "find_sessions_overlapping",
    "first_open_slot",
    "instructors_free_at",
    "lock_instructor",
    "open_slots",
    "utc_now",
    "validate_booking_window",
]

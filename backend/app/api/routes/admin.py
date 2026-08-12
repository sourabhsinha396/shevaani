"""Superuser session management.

Every mutation re-checks the role here — the frontend `/admin` guard is UX, not
security.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, Superuser
from app.api.serializers import (
    build_session_admin_out,
    build_site_config,
    seat_counts,
    waitlist_counts,
)
from app.api.serializers import session_roster as roster_for
from app.core.config import settings
from app.integrations import fireflies
from app.models.billing import CreditLedger
from app.models.booking import Booking
from app.models.contact import ContactMessage
from app.models.enums import (
    SEAT_HOLDING_STATUSES,
    CreditReason,
    SessionKind,
    SessionStatus,
    UserRole,
)
from app.models.session import Session
from app.models.user import GoogleCredential, User
from app.schemas.admin import (
    AnalyticsOut,
    CancellationImpactOut,
    ContactHandledIn,
    CreditAdjustByEmailIn,
    CreditAdjustByEmailOut,
    CreditAdjustIn,
    CreditBalanceOut,
    InstructorAdminIn,
    InstructorAdminOut,
    LearnerBookingOut,
    LearnerDetailOut,
    LearnerSummaryOut,
    LedgerEntryOut,
)
from app.schemas.common import Message
from app.schemas.contact import ContactMessageOut
from app.schemas.session import (
    CancelIn,
    GroupSessionCreateIn,
    GroupSessionUpdateIn,
    RescheduleIn,
    SessionAdminOut,
)
from app.schemas.settings import SiteConfigIn, SiteConfigOut
from app.services import analytics as analytics_service
from app.services import booking as booking_service
from app.services import credits, session_admin, site_settings
from app.services.errors import Conflict, NotFound
from app.services.scheduling import utc_now
from app.services.transcripts import MEET_CODE
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


@router.get("/sessions/{session_id}", response_model=SessionAdminOut)
async def get_session(session_id: uuid.UUID, db: DbSession, _: Superuser) -> SessionAdminOut:
    return await _serialize(db, await _load(db, session_id))


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
        slug=payload.slug,
        topic=payload.topic,
        description=payload.description,
        prep_material_url=payload.prep_material_url,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        min_seats=payload.min_seats,
        max_seats=payload.max_seats,
        price_credits=payload.price_credits,
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
        slug=payload.slug,
        topic=payload.topic,
        description=payload.description,
        prep_material_url=payload.prep_material_url,
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


@router.delete("/sessions/{session_id}", response_model=Message)
async def delete_session(session_id: uuid.UUID, db: DbSession, _: Superuser) -> Message:
    """Hard-delete a session — for drafts, test rows and cancelled sessions.

    Refused while any booking is live or is attendance history; cancel first for
    the former, sqladmin for the latter. The Calendar event's ids are captured
    before the row goes, because the cleanup job can no longer look them up.
    """
    session = await _load(db, session_id)
    instructor_id = session.instructor_id
    event_id = session.meeting.calendar_event_id if session.meeting else None

    await session_admin.delete_group_session(db, session)
    await db.commit()

    if event_id:
        await queue.enqueue("delete_calendar_event", str(instructor_id), event_id)
    return Message(detail="Session deleted.")


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


@router.post("/sessions/{session_id}/invite-notetaker", response_model=Message)
async def invite_notetaker(session_id: uuid.UUID, db: DbSession, _: Superuser) -> Message:
    """Send the Fireflies bot into this session's Meet right now.

    The dispatch cron does the same on a clock, but only inside the first
    15 minutes after start and only from a running worker. The button covers
    everything else: local dev without the worker, a bot that got kicked, a
    meeting that started late. Stamping ``notetaker_dispatched_at`` keeps the
    cron from sending a second bot after us.
    """
    if not settings.fireflies_configured:
        raise Conflict("Fireflies is not configured (FIREFLIES_API_KEY).")

    session = await _load(db, session_id)
    meeting = session.meeting
    if meeting is None or not meeting.join_url:
        raise Conflict("This session has no Meet link for the bot to join.")

    duration = int((session.ends_at - session.starts_at).total_seconds() // 60)
    try:
        ok = await fireflies.add_to_live_meeting(
            meeting_link=meeting.join_url,
            title=session.title,
            duration_minutes=duration,
        )
    except fireflies.FirefliesAPIError as exc:
        raise Conflict(f"Fireflies: {exc}") from exc
    if not ok:
        raise Conflict(
            "Fireflies declined the invite — the bot can only join a meeting "
            "that is live, so make sure someone is in the room."
        )

    meeting.notetaker_dispatched_at = utc_now()
    await db.commit()
    return Message(detail="Bot invited — admit it from the Meet lobby.")


@router.post("/sessions/{session_id}/fetch-transcript", response_model=Message)
async def fetch_transcript(session_id: uuid.UUID, db: DbSession, _: Superuser) -> Message:
    """Pull this session's Fireflies transcript without waiting for the webhook.

    Production learns about transcripts from ``meeting.transcribed``; a local
    backend has no public URL for Fireflies to call, so nothing would ever
    arrive. This asks Fireflies for transcripts created around the session,
    matches by Meet code, and hands the id to the same ingest job the webhook
    would have enqueued — one pipeline, two doorbells.
    """
    if not settings.fireflies_configured:
        raise Conflict("Fireflies is not configured (FIREFLIES_API_KEY).")

    session = await _load(db, session_id)
    join_url = (session.meeting.join_url if session.meeting else None) or ""
    code_match = MEET_CODE.search(join_url)
    if code_match is None:
        raise Conflict("This session has no Meet link to match a transcript against.")

    try:
        recent = await fireflies.list_transcripts_since(
            # An hour of slack: the bot may join late, and Fireflies stamps
            # the transcript with its own notion of when the meeting was.
            session.starts_at - timedelta(hours=1)
        )
    except fireflies.FirefliesAPIError as exc:
        raise Conflict(f"Fireflies: {exc}") from exc

    code = code_match.group(1).lower()
    found = next((t for t in recent if code in (t.meeting_link or "").lower()), None)
    if found is None:
        # Conflict, not NotFound: a 404 here would be indistinguishable from
        # "this route/session doesn't exist" in the network tab.
        raise Conflict(
            "Fireflies has no transcript for this Meet yet — transcription usually "
            "lands a few minutes after the call ends. Try again shortly."
        )

    await queue.enqueue("ingest_fireflies_transcript", found.id)
    return Message(detail="Transcript found — ingesting now. Refresh in a few seconds.")


@router.get("/sessions/{session_id}/roster")
async def session_roster(session_id: uuid.UUID, db: DbSession, _: Superuser) -> dict:
    await _load(db, session_id)
    return await roster_for(db, session_id)


@router.get("/sessions/{session_id}/cancellation-impact", response_model=CancellationImpactOut)
async def cancellation_impact(
    session_id: uuid.UUID, db: DbSession, _: Superuser
) -> CancellationImpactOut:
    """What cancelling would cost, so the confirm dialog can say it out loud.

    Cancelling a session refunds every live booking regardless of the usual
    12-hour cutoff, which is not obvious from the button.
    """
    session = await _load(db, session_id)
    return CancellationImpactOut(**await booking_service.cancellation_impact(db, session))


@router.post("/bookings/{booking_id}/attendance", response_model=Message)
async def mark_attendance(
    booking_id: uuid.UUID, db: DbSession, _: Superuser, attended: Annotated[bool, Query()] = True
) -> Message:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise NotFound("Booking not found.")
    await booking_service.record_attendance(db, booking, attended=attended)
    return Message(detail="Attendance recorded.")


# ------------------------------------------------------------------ learners


async def _learner_summary(db: DbSession, user: User) -> LearnerSummaryOut:
    upcoming = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.learner_id == user.id,
            Booking.status.in_(SEAT_HOLDING_STATUSES),
            Booking.starts_at >= utc_now(),
        )
    )
    return LearnerSummaryOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        timezone=user.timezone,
        created_at=user.created_at,
        balance=await credits.balance(db, user.id),
        upcoming_bookings=int(upcoming.scalar_one()),
    )


@router.get("/learners", response_model=list[LearnerSummaryOut])
async def list_learners(
    db: DbSession,
    _: Superuser,
    query: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LearnerSummaryOut]:
    """Name/email search. Support questions arrive as "someone called Priya",
    so this matches on both rather than requiring an exact address."""
    conditions = [User.role == UserRole.LEARNER]
    if query:
        pattern = f"%{query.strip().lower()}%"
        conditions.append(
            func.lower(User.full_name).like(pattern) | func.lower(User.email).like(pattern)
        )

    result = await db.execute(
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [await _learner_summary(db, user) for user in result.scalars().all()]


@router.get("/learners/{learner_id}", response_model=LearnerDetailOut)
async def learner_detail(
    learner_id: uuid.UUID, db: DbSession, _: Superuser
) -> LearnerDetailOut:
    user = await db.get(User, learner_id)
    if user is None:
        raise NotFound("Learner not found.")

    bookings = await db.execute(
        select(Booking)
        # Both parents: a booking hangs off exactly one of them, and a learner's
        # history is the two kinds interleaved.
        .options(selectinload(Booking.session), selectinload(Booking.one_on_one))
        .where(Booking.learner_id == learner_id)
        .order_by(Booking.starts_at.desc())
        .limit(100)
    )
    ledger = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.user_id == learner_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(100)
    )

    return LearnerDetailOut(
        learner=await _learner_summary(db, user),
        bookings=[
            LearnerBookingOut(
                id=b.id,
                session_id=b.parent_id,
                session_title=(b.session or b.one_on_one).title,
                status=b.status,
                starts_at=b.starts_at,
                ends_at=b.ends_at,
                credits_spent=b.credits_spent,
                waitlist_position=b.waitlist_position,
                cancelled_at=b.cancelled_at,
            )
            for b in bookings.scalars().all()
        ],
        ledger=[LedgerEntryOut.model_validate(e) for e in ledger.scalars().all()],
    )


async def _apply_credit_adjustment(
    db: DbSession, user: User, *, delta: int, note: str | None, actor: User
) -> int:
    """Both directions are ledger rows; nothing is ever edited in place, so the
    balance stays reconstructible from history."""
    await credits.lock_user(db, user.id)
    note = note or f"Adjusted by {actor.email}"

    if delta > 0:
        await credits.grant(db, user.id, delta, CreditReason.ADMIN_GRANT, note=note)
    else:
        # spend() refuses to go negative — a balance below zero would be a bug
        # the ledger could never explain.
        await credits.spend(db, user.id, -delta, CreditReason.ADMIN_REVOKE, note=note)

    return await credits.balance(db, user.id)


@router.post("/learners/{learner_id}/credits", response_model=CreditBalanceOut)
async def adjust_credits(
    learner_id: uuid.UUID, payload: CreditAdjustIn, db: DbSession, actor: Superuser
) -> CreditBalanceOut:
    """Hand-grant or claw back credits — what `make credits` does, from the UI."""
    user = await db.get(User, learner_id)
    if user is None:
        raise NotFound("Learner not found.")

    balance = await _apply_credit_adjustment(
        db, user, delta=payload.delta, note=payload.note, actor=actor
    )
    return CreditBalanceOut(balance=balance)


@router.post("/credits", response_model=CreditAdjustByEmailOut)
async def adjust_credits_by_email(
    payload: CreditAdjustByEmailIn, db: DbSession, actor: Superuser
) -> CreditAdjustByEmailOut:
    """The same adjustment, addressed by email — and for *any* role, where the
    learner search shows only learners. This is how a superuser or instructor
    account gets test credits without SQL."""
    result = await db.execute(
        select(User).where(func.lower(User.email) == payload.email.strip().lower())
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFound(f"No account uses {payload.email.strip()}.")

    balance = await _apply_credit_adjustment(
        db, user, delta=payload.delta, note=payload.note, actor=actor
    )
    return CreditAdjustByEmailOut(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.value,
        balance=balance,
    )


# --------------------------------------------------------------- instructors


@router.get("/instructors", response_model=list[InstructorAdminOut])
async def list_instructors_admin(db: DbSession, _: Superuser) -> list[InstructorAdminOut]:
    """Includes Google connection status — an instructor who hasn't connected
    can't host, so the session form must be able to grey them out."""
    result = await db.execute(
        select(User, GoogleCredential)
        .outerjoin(GoogleCredential, GoogleCredential.user_id == User.id)
        .where(User.role.in_([UserRole.INSTRUCTOR, UserRole.SUPERUSER]))
        .order_by(User.full_name)
    )
    rows = result.all()

    upcoming = await db.execute(
        select(Session.instructor_id, func.count(Session.id))
        .where(
            Session.starts_at >= utc_now(),
            Session.status.in_([SessionStatus.DRAFT, SessionStatus.PUBLISHED]),
        )
        .group_by(Session.instructor_id)
    )
    counts = {row[0]: int(row[1]) for row in upcoming.all()}

    return [
        InstructorAdminOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            headline=user.headline,
            bio=user.bio,
            google_connected=credential is not None and credential.revoked_at is None,
            google_email=credential.google_email if credential else None,
            upcoming_sessions=counts.get(user.id, 0),
        )
        for user, credential in rows
    ]


@router.patch("/instructors/{instructor_id}", response_model=Message)
async def update_instructor(
    instructor_id: uuid.UUID, payload: InstructorAdminIn, db: DbSession, _: Superuser
) -> Message:
    """Edit an existing instructor. Creating one stays in the CLI (decision 10)
    — there is deliberately no self-service path into the role."""
    user = await db.get(User, instructor_id)
    if user is None or user.role not in (UserRole.INSTRUCTOR, UserRole.SUPERUSER):
        raise NotFound("Instructor not found.")

    if payload.is_active is False:
        upcoming = await db.execute(
            select(func.count(Session.id)).where(
                Session.instructor_id == instructor_id,
                Session.status == SessionStatus.PUBLISHED,
                Session.starts_at >= utc_now(),
            )
        )
        live = int(upcoming.scalar_one())
        if live:
            # Deactivating hides them from slot generation but does not cancel
            # anything, so the sessions would sit there hostless.
            raise Conflict(
                f"{user.full_name} still has {live} published session(s) ahead. "
                "Cancel or reassign those first."
            )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    return Message(detail="Instructor updated.")


# ----------------------------------------------------------------- contact


@router.get("/contact-messages", response_model=list[ContactMessageOut])
async def list_contact_messages(
    db: DbSession,
    _: Superuser,
    handled: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ContactMessageOut]:
    conditions = []
    if handled is True:
        conditions.append(ContactMessage.handled_at.is_not(None))
    elif handled is False:
        conditions.append(ContactMessage.handled_at.is_(None))

    result = await db.execute(
        select(ContactMessage)
        .where(*conditions)
        .order_by(ContactMessage.created_at.desc())
        .limit(limit)
    )
    return [ContactMessageOut.model_validate(m) for m in result.scalars().all()]


@router.post("/contact-messages/{message_id}/handled", response_model=Message)
async def mark_contact_handled(
    message_id: uuid.UUID, payload: ContactHandledIn, db: DbSession, _: Superuser
) -> Message:
    message = await db.get(ContactMessage, message_id)
    if message is None:
        raise NotFound("Message not found.")
    message.handled_at = utc_now()
    message.handled_note = payload.note
    return Message(detail="Marked as handled.")


# ------------------------------------------------------------- analytics


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(
    db: DbSession,
    _: Superuser,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> AnalyticsOut:
    """The numbers screen: growth, money, bookings, referrals.

    Read-only aggregates, computed fresh — see ``services.analytics`` for why
    nothing is cached and why days are business-timezone days.
    """
    return await analytics_service.overview(db, days)


# ------------------------------------------------------------ site config


@router.get("/config", response_model=SiteConfigOut)
async def read_site_config(db: DbSession, _: Superuser) -> SiteConfigOut:
    """The same flags ``GET /config`` serves, read fresh.

    The admin form deliberately does not reuse the public endpoint: that one is
    read through the frontend's ISR cache and can be up to a minute behind, and
    a settings screen showing a stale value is a settings screen that reports
    your own save as not having happened.
    """
    return build_site_config(await site_settings.load(db))


@router.patch("/config", response_model=SiteConfigOut)
async def update_site_config(
    payload: SiteConfigIn, db: DbSession, _: Superuser
) -> SiteConfigOut:
    """Flip one or more flags. Absent fields are left alone.

    Partial rather than whole-object so two people editing different switches
    cannot overwrite each other, and so a frontend that predates a newly added
    flag cannot reset it by omission.
    """
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    return build_site_config(await site_settings.update(db, changes))

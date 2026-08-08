"""Background jobs.

Everything that touches Google, or that has to happen on a clock, lives here.
The booking path never calls Google directly — a session is committed first and
the meeting is created by :func:`sync_session_meeting` afterwards, so an outage
at Google degrades the admin view instead of breaking bookings.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import SessionLocal
from app.core.security import decrypt_secret
from app.integrations import google_calendar
from app.integrations.google_calendar import GoogleAPIError
from app.models.enums import MeetingStatus, SessionStatus
from app.models.session import Session, SessionMeeting
from app.models.user import GoogleCredential
from app.services import booking as booking_service
from app.services import session_admin
from app.services.scheduling import utc_now

logger = logging.getLogger(__name__)

MAX_MEETING_ATTEMPTS = 5


async def _access_token_for(db, instructor_id: uuid.UUID) -> tuple[str, str]:
    credential = await db.get(GoogleCredential, instructor_id)
    if credential is None or not credential.is_usable:
        raise GoogleAPIError(
            "Instructor has no usable Google connection.", retryable=False
        )
    token = await google_calendar.refresh_access_token(
        decrypt_secret(credential.refresh_token_encrypted)
    )
    return token, credential.google_email


def _describe(session: Session) -> str:
    parts = [session.description or ""]
    if session.prep_material_url:
        parts.append(f"Prep material: {session.prep_material_url}")
    parts.append(
        "Learners join through Shevaani and will appear in the lobby — "
        "please join a few minutes early to admit them."
    )
    return "\n\n".join(p for p in parts if p)


async def sync_session_meeting(ctx: dict, session_id: str) -> str:
    """Create or move the Calendar event (and therefore the Meet link) for a session.

    Idempotent: the Google request id is derived from the session id, so a retry
    reuses the same conference rather than minting a second one.
    """
    async with SessionLocal() as db:
        session = await db.get(
            Session, uuid.UUID(session_id), options=[selectinload(Session.meeting)]
        )
        if session is None:
            return "session gone"
        if session.status == SessionStatus.CANCELLED:
            return "session cancelled"

        meeting = session.meeting
        if meeting is None:
            meeting = SessionMeeting(session_id=session.id)
            db.add(meeting)
            await db.flush()

        meeting.attempts += 1
        try:
            access_token, google_email = await _access_token_for(db, session.instructor_id)

            if meeting.calendar_event_id:
                await google_calendar.update_event_time(
                    access_token,
                    event_id=meeting.calendar_event_id,
                    summary=session.title,
                    description=_describe(session),
                    starts_at=session.starts_at,
                    ends_at=session.ends_at,
                )
            else:
                event = await google_calendar.create_event_with_meet(
                    access_token,
                    session_id=session.id,
                    summary=session.title,
                    description=_describe(session),
                    starts_at=session.starts_at,
                    ends_at=session.ends_at,
                )
                meeting.calendar_event_id = event.event_id
                meeting.join_url = event.join_url

            meeting.host_google_email = google_email
            meeting.last_error = None
            meeting.status = (
                MeetingStatus.READY if meeting.join_url else MeetingStatus.FAILED
            )
            if not meeting.join_url:
                meeting.last_error = "Google returned no Meet link for the event."
        except GoogleAPIError as exc:
            meeting.last_error = str(exc)
            meeting.status = (
                MeetingStatus.PENDING
                if exc.retryable and meeting.attempts < MAX_MEETING_ATTEMPTS
                else MeetingStatus.FAILED
            )
            await db.commit()
            if meeting.status == MeetingStatus.PENDING:
                raise  # let ARQ retry with backoff
            logger.error("Meeting sync failed permanently for %s: %s", session_id, exc)
            return f"failed: {exc}"

        await db.commit()
        return meeting.status.value


async def remove_session_meeting(ctx: dict, session_id: str) -> str:
    """Delete the Calendar event when a session is cancelled."""
    async with SessionLocal() as db:
        session = await db.get(
            Session, uuid.UUID(session_id), options=[selectinload(Session.meeting)]
        )
        if session is None or session.meeting is None:
            return "nothing to remove"

        meeting = session.meeting
        if not meeting.calendar_event_id:
            return "no event"

        try:
            access_token, _ = await _access_token_for(db, session.instructor_id)
            await google_calendar.delete_event(
                access_token, event_id=meeting.calendar_event_id
            )
        except GoogleAPIError as exc:
            meeting.last_error = f"Delete failed: {exc}"
            await db.commit()
            return f"failed: {exc}"

        meeting.calendar_event_id = None
        meeting.join_url = None
        meeting.status = MeetingStatus.PENDING
        await db.commit()
        return "removed"


async def retry_pending_meetings(ctx: dict) -> str:
    """Safety net for sessions whose meeting job died without leaving a retry."""
    async with SessionLocal() as db:
        result = await db.execute(
            select(SessionMeeting)
            .join(Session, Session.id == SessionMeeting.session_id)
            .where(
                SessionMeeting.status == MeetingStatus.PENDING,
                SessionMeeting.attempts < MAX_MEETING_ATTEMPTS,
                Session.status == SessionStatus.PUBLISHED,
                Session.starts_at > utc_now(),
            )
            .limit(50)
        )
        stale = list(result.scalars().all())

    for meeting in stale:
        await ctx["redis"].enqueue_job("sync_session_meeting", str(meeting.session_id))
    return f"requeued {len(stale)}"


async def sweep_expired_holds(ctx: dict) -> str:
    async with SessionLocal() as db:
        released = await booking_service.release_expired_holds(db)
        await db.commit()
    return f"released {released}"


async def auto_cancel_underfilled_sessions(ctx: dict) -> str:
    """Cancel group sessions that won't reach min_seats, refund, and drop the event."""
    async with SessionLocal() as db:
        cancelled = await session_admin.auto_cancel_underfilled(db)
        session_ids = [str(s.id) for s in cancelled]
        await db.commit()

    for session_id in session_ids:
        await ctx["redis"].enqueue_job("remove_session_meeting", session_id)
    return f"cancelled {len(session_ids)}"


async def mark_sessions_completed(ctx: dict) -> str:
    """Flip finished sessions to completed so the catalogue and dashboards stay honest."""
    async with SessionLocal() as db:
        result = await db.execute(
            select(Session).where(
                Session.status == SessionStatus.PUBLISHED,
                Session.ends_at < utc_now() - timedelta(minutes=15),
            )
        )
        sessions = list(result.scalars().all())
        for session in sessions:
            session.status = SessionStatus.COMPLETED
        await db.commit()
    return f"completed {len(sessions)}"

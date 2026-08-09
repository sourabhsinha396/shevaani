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
from app.integrations import email as email_service
from app.integrations import google_calendar, slack
from app.integrations.google_calendar import GoogleAPIError
from app.models.enums import MeetingStatus, SessionStatus
from app.models.session import Session, SessionMeeting
from app.models.user import GoogleCredential, User
from app.services import backups, notifications, session_admin
from app.services import booking as booking_service
from app.services.scheduling import utc_now

logger = logging.getLogger(__name__)

MAX_MEETING_ATTEMPTS = 5


async def _mark_connection_dead(db, credential: GoogleCredential, reason: str) -> None:
    """Retire a Google connection that can no longer produce an access token.

    Refresh tokens die for reasons we cannot fix from here: the instructor
    revoked access, changed their Google password, the grant expired because the
    OAuth app is still unverified (see docs/GOOGLE_MEET.md — that one silently
    caps them at seven days), or our own encryption key was rotated without
    re-encrypting.

    In every case the honest state is "not connected". Leaving the row usable
    would mean every future session for this instructor fails the same way, five
    retries at a time, forever — and `can_host` would keep saying yes, so
    superusers would keep publishing sessions that cannot get a room.
    """
    credential.revoked_at = utc_now()
    await db.flush()

    instructor = await db.get(User, credential.user_id)
    if instructor is not None:
        await email_service.dispatch(
            email_service.build_google_connection_lost(
                to=instructor.email,
                full_name=instructor.full_name,
                google_email=credential.google_email,
            )
        )
        await slack.deliver(
            slack.google_connection_lost(full_name=instructor.full_name, reason=reason)
        )
    logger.warning("Google connection retired for %s: %s", credential.user_id, reason)


async def _access_token_for(db, instructor_id: uuid.UUID) -> tuple[str, str]:
    credential = await db.get(GoogleCredential, instructor_id)
    if credential is None or not credential.is_usable:
        raise GoogleAPIError(
            "Instructor has no usable Google connection.", retryable=False
        )

    try:
        refresh_token = decrypt_secret(credential.refresh_token_encrypted)
    except Exception as exc:  # noqa: BLE001 — InvalidToken, or no key configured
        # The stored ciphertext cannot be read with the key this process has.
        # Retrying will not change that, and the instructor has to reconnect.
        await _mark_connection_dead(db, credential, "stored refresh token is unreadable")
        raise GoogleAPIError(
            "The stored Google credential could not be decrypted. "
            "The instructor must reconnect their account.",
            retryable=False,
        ) from exc

    try:
        token = await google_calendar.refresh_access_token(refresh_token)
    except GoogleAPIError as exc:
        # 400 is Google's `invalid_grant`: the token is gone, not busy. Anything
        # else (429, 5xx) is transient and keeps its retry.
        if exc.status_code == 400:
            await _mark_connection_dead(db, credential, str(exc))
        raise

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
            # Out of retries. PLAN calls this the one thing in the system that can
            # fail quietly: the session still exists, still has learners, and
            # simply has no room. Slack is what stops it being quiet.
            await slack.deliver(
                slack.meeting_failed(
                    title=session.title, session_id=str(session.id), error=str(exc)
                )
            )
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
    """Cancel group sessions that won't reach min_seats, refund, and drop the event.

    The learner emails are dispatched inside `cancel_session`; the Slack line is
    here because it is about the *sweep*, not about any one learner — a superuser
    reading it may want to reach out, or to ask why a session never filled.
    """
    async with SessionLocal() as db:
        cancelled = await session_admin.auto_cancel_underfilled(db)
        announcements = [
            slack.session_auto_cancelled(
                title=c.session.title,
                seats_taken=c.seats_taken,
                min_seats=c.session.min_seats,
                learners=c.learners_affected,
            )
            for c in cancelled
        ]
        session_ids = [str(c.session.id) for c in cancelled]
        await db.commit()

    for session_id in session_ids:
        await ctx["redis"].enqueue_job("remove_session_meeting", session_id)
    for message in announcements:
        await slack.deliver(message)
    return f"cancelled {len(session_ids)}"


async def send_session_reminders(ctx: dict) -> str:
    """Remind learners about sessions coming up, at each configured offset.

    The session is read *here*, at send time. Enqueuing a reminder when the
    session is created and letting it sit on the queue with a baked-in time would
    cheerfully remind everyone about a session that has since moved or been
    cancelled — the queue has no idea the row changed.
    """
    sent: list[str] = []
    async with SessionLocal() as db:
        for hours in notifications.configured_reminder_offsets():
            count = await notifications.send_due_reminders(db, hours)
            if count:
                sent.append(f"T-{hours}h: {count}")
        await db.commit()
    return ", ".join(sent) or "nothing due"


async def send_email(
    ctx: dict, to: str, subject: str, body: str, to_name: str | None = None
) -> str:
    """The only place an email is actually handed to a provider."""
    delivered = await email_service.deliver(
        email_service.Email(to=to, subject=subject, body=body, to_name=to_name)
    )
    return "sent" if delivered else "not sent"


async def backup_database(ctx: dict) -> str:
    """Nightly pg_dump to object storage.

    A failure here is louder than anywhere else in this module: everything else
    that fails leaves a visible row behind, and a backup that did not happen
    leaves nothing at all. The exception is re-raised after alerting so ARQ
    records the job as failed rather than as a job that returned a sad string.
    """
    try:
        result = await backups.create()
    except Exception as exc:  # noqa: BLE001 — alert on anything, then re-raise
        logger.exception("Nightly backup failed")
        await slack.deliver(slack.backup_failed(error=str(exc)))
        raise
    return str(result)


async def post_slack_message(ctx: dict, text: str) -> str:
    """The only place a Slack webhook is actually called from a request-side
    dispatch. Failures are logged inside `deliver` and never raised — a retry
    storm over a missed notification would be worse than the missed
    notification."""
    return "posted" if await slack.deliver(text) else "not posted"


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

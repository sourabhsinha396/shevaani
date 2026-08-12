"""Background jobs.

Everything that touches Google, or that has to happen on a clock, lives here.
The booking path never calls Google directly — a session is committed first and
the meeting is created by :func:`sync_session_meeting` afterwards, so an outage
at Google degrades the admin view instead of breaking bookings.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import decrypt_secret
from app.integrations import email as email_service
from app.integrations import fireflies, google_calendar, slack
from app.integrations.google_calendar import GoogleAPIError
from app.models.enums import FeedbackStatus, MeetingStatus, SessionStatus, TranscriptStatus
from app.models.feedback import SessionFeedback, SessionTranscript, TranscriptSpeaker
from app.models.session import Session, SessionMeeting
from app.models.user import GoogleCredential, User
from app.services import backups, notifications, session_admin
from app.services import booking as booking_service
from app.services import feedback as feedback_service
from app.services import transcripts as transcript_service
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
    if settings.fireflies_configured:
        parts.append(
            "Shevaani's notes bot (Fireflies.ai Notetaker) will also knock shortly "
            "after the start — please admit it. It records the discussion so every "
            "learner gets a written feedback report."
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


#: How far past its start a session can be and still get the bot sent in.
#: Beyond this, half the discussion is already lost — a partial transcript
#: would produce feedback about a meeting the learners don't recognise.
NOTETAKER_WINDOW_MINUTES = 15

#: Fireflies allows 3 ``addToLiveMeeting`` calls per 20 minutes. Counting rows
#: with a recent ``notetaker_dispatched_at`` reconstructs the rolling window
#: from data we already keep — no Redis counter to drift out of sync, and it
#: survives worker restarts. Failed calls are not counted, which is slightly
#: optimistic; the 429 handler below is the backstop for that.
FIREFLIES_RATE_LIMIT = 3
FIREFLIES_RATE_WINDOW_MINUTES = 20


async def dispatch_notetakers(ctx: dict) -> str:
    """Send the Fireflies bot into meetings whose session just started.

    ``addToLiveMeeting`` only works on an *ongoing* meeting, which is why this
    is a cron and not part of meeting creation. ``notetaker_dispatched_at`` is
    the idempotence key: it is set only on a successful send, so a failed one
    is retried on the next tick until the window closes.
    """
    if not settings.fireflies_configured:
        return "not configured"

    now = utc_now()
    async with SessionLocal() as db:
        recent = await db.scalar(
            select(sa_func.count())
            .select_from(SessionMeeting)
            .where(
                SessionMeeting.notetaker_dispatched_at
                > now - timedelta(minutes=FIREFLIES_RATE_WINDOW_MINUTES)
            )
        )
        budget = FIREFLIES_RATE_LIMIT - (recent or 0)
        if budget <= 0:
            return "rate window exhausted, 0 sent"

        result = await db.execute(
            select(Session)
            .join(SessionMeeting, SessionMeeting.session_id == Session.id)
            .options(selectinload(Session.meeting))
            .where(
                Session.status == SessionStatus.PUBLISHED,
                Session.starts_at <= now,
                Session.starts_at > now - timedelta(minutes=NOTETAKER_WINDOW_MINUTES),
                SessionMeeting.status == MeetingStatus.READY,
                SessionMeeting.notetaker_dispatched_at.is_(None),
            )
            # Oldest start first: those sessions fall out of the dispatch
            # window soonest, so they get the scarce rate-limit slots.
            .order_by(Session.starts_at)
        )
        sessions = list(result.scalars().all())

        sent = 0
        for session in sessions:
            if sent >= budget:
                # Remaining sessions wait for the next tick; anything still
                # inside its 15-minute window gets picked up then.
                logger.info(
                    "Notetaker rate budget spent, %d session(s) deferred",
                    len(sessions) - sent,
                )
                break
            meeting = session.meeting
            if not meeting or not meeting.join_url:
                continue
            duration = int((session.ends_at - session.starts_at).total_seconds() // 60)
            try:
                ok = await fireflies.add_to_live_meeting(
                    meeting_link=meeting.join_url,
                    title=session.title,
                    duration_minutes=duration,
                )
            except fireflies.FirefliesAPIError as exc:
                logger.warning("Notetaker dispatch failed for %s: %s", session.id, exc)
                if exc.rate_limited:
                    # Fireflies says the window is spent (our count was
                    # optimistic — failed calls consume slots too). More
                    # calls this tick would only burn the next window.
                    break
                # Anything else is a blip: the next tick retries while the
                # session's window is open. Log rather than alert — a session
                # with no transcript is a degraded extra, not an incident.
                continue
            if ok:
                meeting.notetaker_dispatched_at = utc_now()
                sent += 1
        await db.commit()
    return f"dispatched {sent}/{len(sessions)}"


_MEET_CODE = re.compile(r"meet\.google\.com/([a-z0-9-]+)", re.IGNORECASE)


async def ingest_fireflies_transcript(ctx: dict, provider_transcript_id: str) -> str:
    """Fetch a finished transcript, attach it to its session, resolve speakers.

    Matching is by Meet code: the transcript's ``meeting_link`` and the
    meeting's ``join_url`` both contain it. A transcript we can't place is
    normal — the account may also record meetings that aren't sessions — so
    it's an ignore, not an error.
    """
    if not settings.fireflies_configured:
        return "not configured"

    transcript_data = await fireflies.fetch_transcript(provider_transcript_id)
    code_match = _MEET_CODE.search(transcript_data.meeting_link or "")
    if code_match is None:
        return "no meet link"

    async with SessionLocal() as db:
        result = await db.execute(
            select(SessionMeeting).where(
                SessionMeeting.session_id.is_not(None),
                SessionMeeting.join_url.ilike(f"%{code_match.group(1)}%"),
            )
        )
        meeting = result.scalar_one_or_none()
        if meeting is None:
            return "no matching session"

        existing = await db.execute(
            select(SessionTranscript).where(
                SessionTranscript.provider_transcript_id == provider_transcript_id
            )
        )
        transcript = existing.scalar_one_or_none()
        if transcript is None:
            transcript = SessionTranscript(
                session_id=meeting.session_id,
                provider_transcript_id=provider_transcript_id,
            )
            db.add(transcript)

        transcript.duration_minutes = transcript_data.duration_minutes
        transcript.sentences = [
            {"speaker": s.speaker, "text": s.text, "start": s.start, "end": s.end}
            for s in transcript_data.sentences
        ]
        await db.flush()

        fully_resolved = await transcript_service.resolve_speakers(db, transcript)
        if fully_resolved:
            await transcript_service.learn_aliases(db, transcript)
        transcript_id = str(transcript.id)
        session = await db.get(Session, meeting.session_id)
        title = session.title if session else "?"
        unmatched = [
            s.speaker_label
            for s in (
                await db.execute(
                    select(TranscriptSpeaker).where(
                        TranscriptSpeaker.transcript_id == transcript.id
                    )
                )
            ).scalars()
            if s.user_id is None and not s.ignored
        ]
        await db.commit()

    if fully_resolved:
        await ctx["redis"].enqueue_job("generate_session_feedback", transcript_id)
        return "resolved"

    await slack.deliver(
        f"Transcript for “{title}” needs speaker review — "
        f"unmatched: {', '.join(unmatched)}. Map them in /admin (Transcript speakers), "
        "the sweep will pick it up."
    )
    return f"needs review ({len(unmatched)} unmatched)"


async def sweep_review_transcripts(ctx: dict) -> str:
    """Close the human-review loop.

    An admin fixes speaker mappings as plain row edits in sqladmin — nothing
    there can enqueue a job. This sweep notices NEEDS_REVIEW transcripts whose
    speakers are now all mapped or ignored, learns the aliases, and queues
    generation. Also re-queues RESOLVED transcripts that somehow have no
    feedback rows (a generation that died gets a second chance).
    """
    requeued = 0
    async with SessionLocal() as db:
        result = await db.execute(
            select(SessionTranscript)
            .options(selectinload(SessionTranscript.speakers))
            .where(SessionTranscript.status == TranscriptStatus.NEEDS_REVIEW)
        )
        for transcript in result.scalars():
            if not transcript.speakers:
                continue
            if all(s.user_id is not None or s.ignored for s in transcript.speakers):
                transcript.status = TranscriptStatus.RESOLVED
                # Admin-set rows have no resolved_via yet — stamp them so
                # alias learning and future audits know a human decided.
                for s in transcript.speakers:
                    if s.user_id is not None and s.resolved_via is None:
                        s.resolved_via = "admin"
                await transcript_service.learn_aliases(db, transcript)
                await ctx["redis"].enqueue_job(
                    "generate_session_feedback", str(transcript.id)
                )
                requeued += 1
        await db.commit()
    return f"requeued {requeued}"


async def generate_session_feedback(ctx: dict, transcript_id: str) -> str:
    """Draft the per-learner reports. The expensive step, so it is its own job
    with its own timeout — one model call over the whole transcript."""
    if not settings.feedback_configured:
        return "not configured"

    async with SessionLocal() as db:
        try:
            written = await feedback_service.generate_feedback(db, uuid.UUID(transcript_id))
        except Exception as exc:  # noqa: BLE001 — record the failure on the row
            transcript = await db.get(SessionTranscript, uuid.UUID(transcript_id))
            if transcript is not None:
                transcript.last_error = str(exc)[:2000]
            await db.commit()
            raise  # let ARQ retry with backoff
        transcript = await db.get(
            SessionTranscript,
            uuid.UUID(transcript_id),
            options=[selectinload(SessionTranscript.session)],
        )
        title = transcript.session.title if transcript and transcript.session else "?"
        if transcript is not None:
            transcript.last_error = None
        await db.commit()

    if written:
        await slack.deliver(
            f"Feedback drafts ready for “{title}” — {written} report(s). "
            "Review and publish in /admin (Session feedback)."
        )
    return f"wrote {written}"


async def finalize_session_feedback(ctx: dict, transcript_id: str) -> str:
    """The review surface's one big button: regenerate from the current
    mappings, then publish everything.

    Deliberately allowed to overwrite published rows — unlike the automatic
    pipeline, this runs because an instructor just said "the mappings are
    right, ship it", and stale reports from before a remap are exactly what
    they're asking to replace.
    """
    if not settings.feedback_configured:
        return "not configured"

    tid = uuid.UUID(transcript_id)
    async with SessionLocal() as db:
        # Everything generate_feedback will touch, loaded up front: its own
        # db.get() hits the identity map and does NOT re-apply loader options,
        # so anything missing here would be a lazy load on an async session.
        transcript = await db.get(
            SessionTranscript,
            tid,
            options=[
                selectinload(SessionTranscript.speakers).selectinload(TranscriptSpeaker.user),
                selectinload(SessionTranscript.session).selectinload(Session.instructor),
            ],
        )
        if transcript is None:
            return "transcript gone"
        if any(s.user_id is None and not s.ignored for s in transcript.speakers):
            return "unmatched speakers"

        transcript.status = TranscriptStatus.RESOLVED
        for s in transcript.speakers:
            if s.user_id is not None and s.resolved_via is None:
                s.resolved_via = "admin"
        await transcript_service.learn_aliases(db, transcript)

        # Reopen published rows so generation refreshes them too, then publish
        # the lot in the same transaction as the regenerated text.
        existing = await db.execute(
            select(SessionFeedback).where(SessionFeedback.transcript_id == tid)
        )
        for row in existing.scalars():
            row.status = FeedbackStatus.DRAFT
        await db.flush()

        written = await feedback_service.generate_feedback(db, tid)

        now = utc_now()
        rows = await db.execute(
            select(SessionFeedback).where(SessionFeedback.transcript_id == tid)
        )
        published = 0
        for row in rows.scalars():
            row.status = FeedbackStatus.PUBLISHED
            row.published_at = now
            published += 1
        await db.commit()

    return f"regenerated {written}, published {published}"


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

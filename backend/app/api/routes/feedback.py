"""Group-discussion feedback, both sides of it.

**Learners** see published reports only. Drafts belong to the review surface —
a learner never sees the state machine, only the finished report.

**Instructors and superusers** get the review surface under ``/manage``: fix a
speaker mapping the resolver got wrong, finalize (regenerate + publish in one
click), and email a learner their report. Instructors see their own sessions'
transcripts; superusers see all.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Instructor
from app.integrations import email as email_service
from app.models.booking import Booking
from app.models.enums import FeedbackStatus, UserRole
from app.models.feedback import SessionFeedback, SessionTranscript, TranscriptSpeaker
from app.models.session import Session
from app.schemas.feedback import (
    FeedbackOut,
    ManageReportOut,
    ManageTranscriptDetail,
    ManageTranscriptSummary,
    RosterUserOut,
    SpeakerMapIn,
    SpeakerOut,
)
from app.services.scheduling import utc_now
from app.services.transcripts import roster_for_session
from app.workers import queue

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _serialize(feedback: SessionFeedback, session: Session) -> FeedbackOut:
    return FeedbackOut(
        id=feedback.id,
        session_id=session.id,
        session_slug=session.slug,
        session_title=session.title,
        session_starts_at=session.starts_at,
        published_at=feedback.published_at,
        report_md=feedback.report_md,
        structured=feedback.structured,
        metrics=feedback.metrics or {},
        score=feedback.score,
    )


@router.get("/me", response_model=list[FeedbackOut])
async def my_feedback(db: DbSession, user: CurrentUser) -> list[FeedbackOut]:
    """Every published report for the caller, newest session first."""
    result = await db.execute(
        select(SessionFeedback, Session)
        .join(Booking, Booking.id == SessionFeedback.booking_id)
        .join(SessionTranscript, SessionTranscript.id == SessionFeedback.transcript_id)
        .join(Session, Session.id == SessionTranscript.session_id)
        .where(
            Booking.learner_id == user.id,
            SessionFeedback.status == FeedbackStatus.PUBLISHED,
        )
        .order_by(Session.starts_at.desc())
    )
    return [_serialize(feedback, session) for feedback, session in result.all()]


@router.get("/sessions/{session_ref}", response_model=FeedbackOut)
async def session_feedback(
    session_ref: str, db: DbSession, user: CurrentUser
) -> FeedbackOut:
    """The caller's report for one session, addressed by slug (the URL the
    dashboard links) or UUID. 404 covers every kind of "not for you": no
    booking, no transcript yet, or not published yet — a learner can't
    distinguish them, and shouldn't."""
    try:
        ref_clause = Session.id == uuid.UUID(session_ref)
    except ValueError:
        ref_clause = Session.slug == session_ref
    result = await db.execute(
        select(SessionFeedback, Session)
        .join(Booking, Booking.id == SessionFeedback.booking_id)
        .join(SessionTranscript, SessionTranscript.id == SessionFeedback.transcript_id)
        .join(Session, Session.id == SessionTranscript.session_id)
        .where(
            ref_clause,
            Booking.learner_id == user.id,
            SessionFeedback.status == FeedbackStatus.PUBLISHED,
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No feedback for this session yet.")
    feedback, session = row
    return _serialize(feedback, session)


# ------------------------------------------------- instructor / superuser view


async def _owned_transcript(
    db: DbSession, transcript_id: uuid.UUID, actor
) -> SessionTranscript:
    """Load a transcript the actor may manage, or 403/404 trying."""
    transcript = await db.get(
        SessionTranscript,
        transcript_id,
        options=[
            selectinload(SessionTranscript.session).selectinload(Session.instructor),
            selectinload(SessionTranscript.speakers),
        ],
    )
    if transcript is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transcript not found.")
    if actor.role != UserRole.SUPERUSER and transcript.session.instructor_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session.")
    return transcript


def _unmatched(transcript: SessionTranscript) -> int:
    return sum(1 for s in transcript.speakers if s.user_id is None and not s.ignored)


async def _report_rows(
    db: DbSession, transcript: SessionTranscript
) -> list[ManageReportOut]:
    result = await db.execute(
        select(SessionFeedback, Booking)
        .join(Booking, Booking.id == SessionFeedback.booking_id)
        .options(selectinload(Booking.learner))
        .where(SessionFeedback.transcript_id == transcript.id)
    )
    return [
        ManageReportOut(
            id=feedback.id,
            learner=RosterUserOut.model_validate(booking.learner),
            status=feedback.status.value,
            report_md=feedback.report_md,
            published_at=feedback.published_at,
            emailed_at=feedback.emailed_at,
        )
        for feedback, booking in result.all()
    ]


def _summary(transcript: SessionTranscript, reports: list[ManageReportOut]) -> dict:
    return {
        "id": transcript.id,
        "session_id": transcript.session_id,
        "session_title": transcript.session.title,
        "session_starts_at": transcript.session.starts_at,
        "status": transcript.status.value,
        "duration_minutes": transcript.duration_minutes,
        "unmatched_speakers": _unmatched(transcript),
        "published_reports": sum(1 for r in reports if r.status == "published"),
        "total_reports": len(reports),
    }


@router.get("/manage/transcripts", response_model=list[ManageTranscriptSummary])
async def manage_list_transcripts(
    db: DbSession, actor: Instructor
) -> list[ManageTranscriptSummary]:
    query = (
        select(SessionTranscript)
        .join(Session, Session.id == SessionTranscript.session_id)
        .options(
            selectinload(SessionTranscript.session),
            selectinload(SessionTranscript.speakers),
        )
        .order_by(Session.starts_at.desc())
        .limit(100)
    )
    if actor.role != UserRole.SUPERUSER:
        query = query.where(Session.instructor_id == actor.id)

    transcripts = (await db.execute(query)).scalars().all()
    return [
        ManageTranscriptSummary(**_summary(t, await _report_rows(db, t)))
        for t in transcripts
    ]


@router.get("/manage/transcripts/{transcript_id}", response_model=ManageTranscriptDetail)
async def manage_transcript_detail(
    transcript_id: uuid.UUID, db: DbSession, actor: Instructor
) -> ManageTranscriptDetail:
    transcript = await _owned_transcript(db, transcript_id, actor)
    reports = await _report_rows(db, transcript)
    roster = await roster_for_session(db, transcript.session)
    return ManageTranscriptDetail(
        **_summary(transcript, reports),
        speakers=[SpeakerOut.model_validate(s) for s in transcript.speakers],
        roster=sorted(
            (RosterUserOut.model_validate(u) for u in roster.values()),
            key=lambda u: u.full_name.lower(),
        ),
        reports=reports,
    )


@router.patch("/manage/speakers/{speaker_id}", response_model=SpeakerOut)
async def manage_map_speaker(
    speaker_id: uuid.UUID, payload: SpeakerMapIn, db: DbSession, actor: Instructor
) -> SpeakerOut:
    """The dropdown's save. Roster-only on purpose: whoever spoke in that room
    was either seated or hosting, and a typo'd free-form user id would
    misdeliver a whole report."""
    speaker = await db.get(TranscriptSpeaker, speaker_id)
    if speaker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Speaker not found.")
    transcript = await _owned_transcript(db, speaker.transcript_id, actor)

    if payload.user_id is not None:
        roster = await roster_for_session(db, transcript.session)
        if payload.user_id not in roster:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "That user is not on this session's roster.",
            )
        taken = {
            s.user_id
            for s in transcript.speakers
            if s.user_id is not None and s.id != speaker.id
        }
        if payload.user_id in taken:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "That user is already mapped to another speaker.",
            )

    speaker.user_id = None if payload.ignored else payload.user_id
    speaker.ignored = payload.ignored
    speaker.resolved_via = (
        "admin" if (payload.ignored or payload.user_id is not None) else None
    )
    speaker.confidence = None
    await db.commit()
    return SpeakerOut.model_validate(speaker)


@router.post("/manage/transcripts/{transcript_id}/finalize")
async def manage_finalize(
    transcript_id: uuid.UUID, db: DbSession, actor: Instructor
) -> dict[str, str]:
    """Regenerate from the current mappings and publish everything — the one
    click that makes reports learner-visible. Runs in the worker; the UI polls
    the detail endpoint to watch it land."""
    transcript = await _owned_transcript(db, transcript_id, actor)
    if _unmatched(transcript):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Map or ignore every speaker first — reports would misattribute otherwise.",
        )
    await queue.enqueue("finalize_session_feedback", str(transcript.id))
    return {"status": "queued"}


@router.post("/manage/reports/{feedback_id}/email")
async def manage_email_report(
    feedback_id: uuid.UUID, db: DbSession, actor: Instructor
) -> dict[str, str]:
    feedback = await db.get(
        SessionFeedback,
        feedback_id,
        options=[selectinload(SessionFeedback.booking).selectinload(Booking.learner)],
    )
    if feedback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    transcript = await _owned_transcript(db, feedback.transcript_id, actor)
    if feedback.status != FeedbackStatus.PUBLISHED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Finalize the feedback before emailing it."
        )

    learner = feedback.booking.learner
    await email_service.dispatch(
        email_service.build_feedback_report(
            to=learner.email,
            full_name=learner.full_name,
            title=transcript.session.title,
            report_md=feedback.report_md,
        )
    )
    feedback.emailed_at = utc_now()
    await db.commit()
    return {"status": "sent"}

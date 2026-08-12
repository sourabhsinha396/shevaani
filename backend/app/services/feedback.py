"""Drafting per-learner feedback reports from a resolved transcript.

One structured model call per session, not per learner: the model needs the
whole discussion to judge collaboration (who built on whose point, who
interrupted whom), and a six-person transcript fits comfortably in one
request. The call goes through OpenRouter's OpenAI-compatible endpoint —
Gemini Flash by default, swappable per .env — with a JSON schema enforced via
``response_format``. The response is keyed by participant and rendered to
markdown *in code*, so every report has the same shape and the instructor
edits prose, not structure.

What the model is asked for is judgment: argument quality, language slips
with the learner's own words quoted back, collaboration behaviour, two or
three concrete suggestions. What it is never asked for is arithmetic — talk
time, turns, and word counts come from ``services/transcripts.py`` and are
appended to the report verbatim.

Reports are born DRAFT. Publishing is a human clicking a dropdown in
sqladmin, and regeneration never touches a published row.
"""

from __future__ import annotations

import json
import logging
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.booking import Booking
from app.models.enums import FeedbackStatus
from app.models.feedback import SessionFeedback, SessionTranscript, TranscriptSpeaker
from app.models.session import Session
from app.services.gd_score import (
    LLM_RUBRIC_DIMENSIONS,
    compute_gd_score,
    deterministic_subscores,
)
from app.services.transcripts import ROSTER_STATUSES, speaker_metrics

logger = logging.getLogger(__name__)

_MAX_OUTPUT_TOKENS = 16000

#: The judgment half of the GD score: twelve anchored 0-5 integers. Built from
#: the scorer's own dimension list so schema and scorer can't drift apart.
_RUBRIC_SCHEMA = {
    "type": "object",
    "properties": {
        name: {"type": "integer", "description": f"0-5. {anchor}"}
        for name, anchor in LLM_RUBRIC_DIMENSIONS.items()
    },
    "required": list(LLM_RUBRIC_DIMENSIONS),
    "additionalProperties": False,
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "participants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "summary": {
                        "type": "string",
                        "description": "2-4 sentences of candid assessment. One clause "
                        "most held them back this session and what closing it would "
                        "change. A critique, not a compliment.",
                    },
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "areas_to_improve": {"type": "array", "items": {"type": "string"}},
                    "language_notes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote": {
                                    "type": "string",
                                    "description": "Their exact words from the transcript.",
                                },
                                "issue": {"type": "string"},
                                "better": {
                                    "type": "string",
                                    "description": "A natural rephrasing.",
                                },
                                "why": {
                                    "type": "string",
                                    "description": "One line on why fixing this changes how "
                                    "the learner comes across. Empty string for minor notes.",
                                },
                                "severity": {
                                    "type": "string",
                                    "enum": ["major", "minor"],
                                    "description": "major = worth practicing before the next "
                                    "session; minor = small polish, shown collapsed.",
                                },
                            },
                            "required": ["quote", "issue", "better", "why", "severity"],
                            "additionalProperties": False,
                        },
                    },
                    "collaboration": {
                        "type": "string",
                        "description": "How they engaged with others: building on points, "
                        "inviting quieter members in, interrupting, dominating.",
                    },
                    "suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-3 specific, practicable next steps.",
                    },
                    "rubric": _RUBRIC_SCHEMA,
                },
                "required": [
                    "user_id",
                    "summary",
                    "strengths",
                    "areas_to_improve",
                    "language_notes",
                    "collaboration",
                    "suggestions",
                    "rubric",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["participants"],
    "additionalProperties": False,
}

_SYSTEM = """You are an experienced English communication coach reviewing the transcript \
of a small group discussion on an English-learning platform. Most learners are Indian \
professionals and students preparing for interviews, B-school admissions, and workplace \
communication. Your feedback will be lightly edited by the session's instructor and then \
shown to each learner.

Write feedback that is warm, specific, and actionable. Every claim should be traceable to \
the transcript; when you comment on language, quote the learner's exact words. Judge \
fluency and structure, not accent. Do not penalise informal but natural English. Do not \
invent things that are not in the transcript, and never attribute one speaker's words to \
another. Address each learner directly as "you".

The opening "summary" is the one section a learner is guaranteed to read, so spend it \
on what they most need to hear, not on reassurance. Open with a brief, honest nod to \
their strongest moment, then name the single biggest thing that held them back — with \
a concrete moment from the transcript — and say plainly what doing it differently would \
have changed. Do not soften it into vagueness ("could be more confident"); point at the \
behaviour ("you raised the strongest data point of the discussion and then let it drop \
the moment someone pushed back"). Critical is not harsh: no sarcasm, no verdicts about \
the person, only about what they did in this session.

Feedback exists to improve the learner, not to prove you listened. Flag a language note \
as "major" only when fixing it would genuinely change how the learner comes across: a \
non-standard idiom, a recurring pattern, a sentence long enough to lose the room. Give \
each major note one "why" line explaining what fixing it buys them. Two or three major \
notes is usually right. One-off slips — a redundant word, a dropped article, fragments \
that are normal in live speech — are "minor"; include at most two of those and leave \
their "why" empty. If a quote reads like a transcription mishear rather than what the \
learner plausibly said, skip it entirely.

You also score each learner on twelve rubric dimensions, each an integer 0-5 against \
the anchor in its schema description: 0 = no evidence in the transcript, 1-2 = attempted \
but weak or hollow, 3 = solid, 4 = strong, 5 = exceptional and consistent throughout. \
Score only from transcript evidence, and when in doubt round down. A behavior counts \
only when it lands: a statistic counts toward facts_figures only if it was relevant and \
the discussion engaged with it; a reference to a peer counts toward genuine_builds only \
if the learner actually extended or challenged that point; initiation is about the \
quality of framing early on, never about merely speaking first; a conclusion must \
synthesize more than one viewpoint. Three or four genuine instances of anything is full \
evidence — quantity beyond that earns nothing more."""


def _transcript_text(sentences: list[dict], label_names: dict[str, str]) -> str:
    lines = []
    for s in sentences:
        name = label_names.get(s.get("speaker", ""))
        if name is None:
            continue
        minutes, seconds = divmod(int(float(s.get("start", 0.0))), 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {name}: {s.get('text', '')}")
    return "\n".join(lines)


_PILLAR_LABELS = {
    "content": "Content",
    "communication": "Communication",
    "collaboration": "Collaboration",
    "leadership": "Leadership",
    "participation": "Participation",
}


def render_report(entry: dict, metrics: dict | None, score: dict | None = None) -> str:
    """The one place report markdown is shaped, so every report looks the same
    and an instructor's edits are edits to prose, not to structure."""
    parts = [f"## How you did\n\n{entry['summary']}"]

    if score and score.get("composite") is not None:
        pillar_lines = "\n".join(
            f"- {label}: **{score['pillars'][key]}**"
            for key, label in _PILLAR_LABELS.items()
            if key in score.get("pillars", {})
        )
        parts.append(
            f"## Your GD score\n\n**{score['composite']} / 100**\n\n{pillar_lines}"
        )

    if metrics:
        minutes = metrics["talk_time_seconds"] / 60
        share = round(metrics["talk_share"] * 100)
        lines = [
            f"- Speaking time: **{minutes:.1f} min** ({share}% of the discussion)",
            f"- Times you took the floor: **{metrics['turns']}**",
            f"- Longest stretch: **{metrics['longest_monologue_seconds'] / 60:.1f} min**",
            f"- Questions you asked: **{metrics['questions_asked']}**",
        ]
        if metrics.get("filler_total"):
            top = sorted(
                (metrics.get("filler_words") or {}).items(), key=lambda kv: -kv[1]
            )[:3]
            listed = ", ".join(f"“{w}” ×{n}" for w, n in top)
            lines.append(f"- Filler words: **{metrics['filler_total']}** ({listed})")
        parts.append("## By the numbers\n\n" + "\n".join(lines))

    if entry["strengths"]:
        parts.append("## What worked\n\n" + "\n".join(f"- {s}" for s in entry["strengths"]))
    if entry["areas_to_improve"]:
        parts.append(
            "## What to work on\n\n" + "\n".join(f"- {s}" for s in entry["areas_to_improve"])
        )
    if entry["language_notes"]:
        # Pre-severity reports have no "severity" key; treat those as major so
        # nothing an instructor already reviewed silently disappears.
        major = [n for n in entry["language_notes"] if n.get("severity", "major") != "minor"]
        minor = [n for n in entry["language_notes"] if n.get("severity") == "minor"]

        def note_line(n: dict) -> str:
            line = (
                f"- You said: *“{n['quote']}”* — {n['issue'].rstrip('.')}. "
                f"Try: *“{n['better']}”*"
            )
            if n.get("why"):
                line += f"\n  - Why it matters: {n['why']}"
            return line

        blocks = []
        if major:
            blocks.append("\n".join(note_line(n) for n in major))
        if minor:
            blocks.append(
                "### Minor polish\n\nSmall slips that didn't change how you came "
                "across — skim these, don't study them.\n\n"
                + "\n".join(note_line(n) for n in minor)
            )
        parts.append("## Language notes\n\n" + "\n\n".join(blocks))
    if entry["collaboration"]:
        parts.append(f"## Working with the group\n\n{entry['collaboration']}")
    if entry["suggestions"]:
        parts.append(
            "## Before your next session\n\n"
            + "\n".join(f"{i}. {s}" for i, s in enumerate(entry["suggestions"], start=1))
        )
    return "\n\n".join(parts)


_SILENT_REPORT = """## How you did

You joined the session but we didn't catch you speaking this time — so there's no \
speaking feedback to give yet. That's completely normal for a first session; the jump \
into a live discussion is the hardest part.

## Before your next session

1. Set yourself one small goal: make a single point in the first ten minutes, even just \
agreeing with someone and adding one sentence of your own.
2. Prepare one opinion on the topic beforehand so you're never searching for content and \
courage at the same time."""


async def _draft_reports(transcript: SessionTranscript, session: Session) -> dict[str, dict]:
    """One model call for the whole room; returns entries keyed by user id."""
    speakers = [s for s in transcript.speakers if s.user_id is not None]
    label_names: dict[str, str] = {}
    participants_desc = []
    for speaker in speakers:
        is_instructor = speaker.user_id == session.instructor_id
        role = "instructor" if is_instructor else "learner"
        label_names[speaker.speaker_label] = speaker.user.full_name
        participants_desc.append(
            f"- {speaker.user.full_name} ({role})"
            + ("" if is_instructor else f" — user_id: {speaker.user_id}")
        )

    prompt = (
        f"Session topic: {session.topic or session.title}\n\n"
        f"Participants:\n" + "\n".join(participants_desc) + "\n\n"
        "Write feedback for every *learner* listed above (skip the instructor), using "
        "each learner's user_id exactly as given.\n\n"
        "Transcript:\n\n" + _transcript_text(transcript.sentences, label_names)
    )

    client = AsyncOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        timeout=300.0,
    )
    response = await client.chat.completions.create(
        model=settings.feedback_model,
        max_tokens=_MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "gd_feedback", "strict": True, "schema": _SCHEMA},
        },
    )
    choice = response.choices[0]
    if choice.finish_reason == "length":
        # A truncated JSON body parses as garbage or not at all; say what
        # actually happened instead of letting json.loads speak for us.
        raise RuntimeError("Feedback generation hit the output-token cap — raise it.")
    text = choice.message.content or ""
    payload = json.loads(text)
    return {p["user_id"]: p for p in payload["participants"]}


async def generate_feedback(db: AsyncSession, transcript_id: uuid.UUID) -> int:
    """Create or refresh DRAFT feedback for every seated learner. Returns how
    many reports were written."""
    transcript = await db.get(
        SessionTranscript,
        transcript_id,
        options=[
            selectinload(SessionTranscript.speakers).selectinload(TranscriptSpeaker.user),
            selectinload(SessionTranscript.session).selectinload(Session.instructor),
        ],
    )
    if transcript is None:
        return 0
    session = transcript.session

    bookings = {
        b.learner_id: b
        for b in (
            await db.execute(
                select(Booking)
                .options(selectinload(Booking.learner))
                .where(
                    Booking.session_id == session.id, Booking.status.in_(ROSTER_STATUSES)
                )
            )
        ).scalars()
    }
    if not bookings:
        return 0

    label_to_user = {
        s.speaker_label: s.user_id for s in transcript.speakers if s.user_id is not None
    }
    metrics = speaker_metrics(transcript.sentences, label_to_user)

    spoke = {uid for uid in label_to_user.values() if uid in bookings}
    entries = await _draft_reports(transcript, session) if spoke else {}

    # Peer comparison: every *learner* who spoke, ranked by talk time. The
    # instructor is left out — outranking (or being outranked by) the host is
    # not a fact about the learner. The same list goes into every report;
    # `is_you` is flipped per reader. First names only.
    ranking = sorted(
        (uid for uid in spoke),
        key=lambda uid: metrics.get(str(uid), {}).get("talk_time_seconds", 0.0),
        reverse=True,
    )
    peer_rows = [
        {
            "user_id": str(uid),
            "name": (bookings[uid].learner.full_name or "Learner").split()[0],
            "talk_time_seconds": metrics.get(str(uid), {}).get("talk_time_seconds", 0.0),
            "talk_share": metrics.get(str(uid), {}).get("talk_share", 0.0),
        }
        for uid in ranking
    ]
    rank_of = {uid: i + 1 for i, uid in enumerate(ranking)}

    def _personal_metrics(learner_id) -> dict:
        own = dict(metrics.get(str(learner_id)) or {})
        own["peers"] = [
            {**{k: v for k, v in p.items() if k != "user_id"}, "is_you": p["user_id"] == str(learner_id)}
            for p in peer_rows
        ]
        own["rank"] = rank_of.get(learner_id)
        own["peer_count"] = len(ranking)
        return own

    existing = {
        f.booking_id: f
        for f in (
            await db.execute(
                select(SessionFeedback).where(SessionFeedback.transcript_id == transcript.id)
            )
        ).scalars()
    }

    written = 0
    for learner_id, booking in bookings.items():
        row = existing.get(booking.id)
        if row is not None and row.status == FeedbackStatus.PUBLISHED:
            continue

        entry = entries.get(str(learner_id))
        user_metrics = metrics.get(str(learner_id))
        score = None
        if learner_id in spoke:
            det = deterministic_subscores(
                transcript.sentences, label_to_user, learner_id, spoke
            )
            if det is not None:
                score = compute_gd_score(
                    det, (entry or {}).get("rubric"), settings.feedback_model
                )
        if entry is not None:
            report = render_report(entry, user_metrics, score)
        elif learner_id in spoke:
            # The model skipped someone who spoke — a bug or a truncation.
            # Leave their slot empty rather than shipping a blank report.
            logger.warning("No feedback entry for learner %s in %s", learner_id, transcript.id)
            continue
        else:
            report = _SILENT_REPORT

        if row is None:
            row = SessionFeedback(booking_id=booking.id, transcript_id=transcript.id)
            db.add(row)
        row.metrics = _personal_metrics(learner_id)
        row.structured = entry
        row.score = score
        row.report_md = report
        row.generated_by = settings.feedback_model if entry is not None else "template"
        row.status = FeedbackStatus.DRAFT
        written += 1

    await db.flush()
    return written

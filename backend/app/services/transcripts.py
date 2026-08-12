"""Matching diarized speakers to real users, and counting what they said.

The identity problem is small on purpose: a group discussion has at most
``max_seats`` learners (six, today) plus the instructor, so every speaker
label is matched against a handful of candidates — not the user table. The
signals, strongest first:

1. **Alias memory** — this user has joined under this exact name before.
2. **Registered name** — exact or fuzzy match against ``full_name``.
3. **Email local-part** — "harshu2004" matches ``harshu2004@gmail.com``.
4. **Elimination** — one unmatched speaker, one unmatched seat, some
   resemblance: that's them.

Anything under the confidence bar is left unmapped for a human — a
``transcript_speakers`` row with an empty user dropdown in sqladmin. Every
confirmed mapping (auto or admin) is written back to ``meet_aliases``, so the
system needs the human a little less each week.

No model calls here. Matching six names and summing talk time are jobs for
code; the LLM's job starts in ``services/feedback.py``.
"""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking
from app.models.enums import BookingStatus, TranscriptStatus
from app.models.feedback import MeetAlias, SessionTranscript, TranscriptSpeaker
from app.models.session import Session
from app.models.user import User
from app.services.scheduling import utc_now

#: A Google Meet code inside any URL — the join key that ties a Fireflies
#: transcript back to its ``session_meetings`` row. Used by the webhook-driven
#: ingest job and the admin "fetch transcript" endpoint alike.
MEET_CODE = re.compile(r"meet\.google\.com/([a-z0-9-]+)", re.IGNORECASE)

#: Confident enough to assign without a human.
AUTO_THRESHOLD = 0.80
#: A label whose best and second-best candidates are closer than this is
#: ambiguous — "Harsh" in a room with two Harshes scores both identically,
#: and a coin flip that mis-attributes a whole report is worse than asking.
AMBIGUITY_MARGIN = 0.10
#: The floor for last-pair elimination — below this even "only one left" is a guess.
ELIMINATION_FLOOR = 0.40

#: Statuses whose booking means "this learner had a seat in the room".
ROSTER_STATUSES = (BookingStatus.CONFIRMED, BookingStatus.ATTENDED, BookingStatus.NO_SHOW)

_BOT_MARKERS = ("fireflies", "notetaker", "fred ")

#: Filler phrases counted per speaker, multi-word first so "you know" is one
#: filler and not a hit on some future single-word entry. Deliberately short of
#: perfect — "like" the verb gets counted with "like" the filler — because a
#: deterministic, explainable count beats a clever one that can't be checked
#: against the transcript.
FILLER_PHRASES = (
    "you know",
    "i mean",
    "kind of",
    "sort of",
    "um",
    "uh",
    "umm",
    "hmm",
    "like",
    "basically",
    "actually",
    "literally",
)

_FILLER_PATTERNS = {
    phrase: re.compile(rf"\b{re.escape(phrase)}\b") for phrase in FILLER_PHRASES
}


def count_fillers(text: str) -> dict[str, int]:
    """Occurrences of each filler phrase in one sentence, lowercased word-boundary
    matches only. Zero-count phrases are omitted."""
    lowered = text.lower()
    counts = {}
    for phrase, pattern in _FILLER_PATTERNS.items():
        n = len(pattern.findall(lowered))
        if n:
            counts[phrase] = n
    return counts


def normalize(name: str) -> str:
    """Lowercase, strip everything but letters/digits/spaces, collapse runs.
    The one normalisation used for matching *and* for alias storage, so the
    two can never disagree."""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokens(name: str) -> list[str]:
    return normalize(name).split()


def looks_like_bot(label: str) -> bool:
    lowered = f"{label.lower()} "
    return any(marker in lowered for marker in _BOT_MARKERS)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def score_candidate(label: str, user: User, aliases: set[str]) -> float:
    """How plausibly this Meet display name is this user. 0–1."""
    norm_label = normalize(label)
    if not norm_label:
        return 0.0

    if norm_label in aliases:
        return 0.98

    norm_name = normalize(user.full_name or "")
    if norm_label == norm_name:
        return 0.97

    scores = [0.0]

    if norm_name:
        scores.append(_similarity(norm_label, norm_name))
        label_tokens, name_tokens = set(_tokens(label)), set(_tokens(user.full_name))
        # "Harsh" vs "Harsh Gupta", or "Gupta Harsh" vs "Harsh Gupta": token
        # containment is stronger evidence than character-level similarity.
        if label_tokens and name_tokens and (
            label_tokens <= name_tokens or name_tokens <= label_tokens
        ):
            scores.append(0.90)

    # People often join with their Google account, whose display name defaults
    # to the address' local part. Compare letters-and-digits only: dots and
    # plus-tags are noise ("harsh.gupta04" vs "harshgupta").
    local_part = (user.email or "").split("@")[0]
    squeezed_label = re.sub(r"[^a-z0-9]", "", norm_label)
    squeezed_local = re.sub(r"[^a-z0-9]", "", local_part.lower())
    if squeezed_label and squeezed_local:
        ratio = _similarity(squeezed_label, squeezed_local)
        # A perfect local-part match is near-certain; scale down from there.
        scores.append(min(0.95, ratio) if ratio > 0.75 else ratio * 0.6)

    return max(scores)


async def roster_for_session(db: AsyncSession, session: Session) -> dict[uuid.UUID, User]:
    """Everyone who could legitimately be speaking: seated learners + instructor."""
    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.learner))
        .where(Booking.session_id == session.id, Booking.status.in_(ROSTER_STATUSES))
    )
    users = {b.learner_id: b.learner for b in result.scalars()}
    users[session.instructor_id] = session.instructor
    return users


async def _aliases_by_user(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, set[str]]:
    if not user_ids:
        return {}
    result = await db.execute(select(MeetAlias).where(MeetAlias.user_id.in_(user_ids)))
    aliases: dict[uuid.UUID, set[str]] = {}
    for alias in result.scalars():
        aliases.setdefault(alias.user_id, set()).add(alias.display_name)
    return aliases


async def resolve_speakers(db: AsyncSession, transcript: SessionTranscript) -> bool:
    """Create/refresh ``transcript_speakers`` rows for every label in the
    transcript. Returns whether the transcript is fully resolved.

    Idempotent and human-respecting: rows a person already mapped (or ignored)
    are never touched, so re-running after an admin fixes one speaker only
    fills in the gaps.
    """
    session = await db.get(
        Session, transcript.session_id, options=[selectinload(Session.instructor)]
    )
    assert session is not None  # noqa: S101 — FK guarantees it
    roster = await roster_for_session(db, session)
    aliases = await _aliases_by_user(db, list(roster))

    existing = {
        s.speaker_label: s
        for s in (
            await db.execute(
                select(TranscriptSpeaker).where(TranscriptSpeaker.transcript_id == transcript.id)
            )
        ).scalars()
    }

    labels = sorted({s["speaker"] for s in transcript.sentences if s.get("speaker")})
    taken = {s.user_id for s in existing.values() if s.user_id is not None}

    # Score every unmapped label against every unclaimed roster user, then
    # assign greedily best-first — so with two Harshes in the room, the better
    # match claims the name and the other Harsh keeps their surname's score.
    def _needs_resolution(label: str) -> bool:
        row = existing.get(label)
        if row is None:
            return True
        return row.user_id is None and not row.ignored and row.resolved_via != "admin"

    unmapped = [label for label in labels if _needs_resolution(label)]

    candidates: dict[str, list[tuple[float, uuid.UUID]]] = {}
    bot_labels: set[str] = set()
    for label in unmapped:
        if looks_like_bot(label):
            bot_labels.add(label)
            continue
        scored = [
            (score_candidate(label, user, aliases.get(user_id, set())), user_id)
            for user_id, user in roster.items()
            if user_id not in taken
        ]
        candidates[label] = sorted((s for s in scored if s[0] > 0), reverse=True)

    # Assign best-first so the confident label claims its user before an
    # ambiguous one gets a look-in: "Harsh Gupta" (0.97) takes Gupta, after
    # which a bare "Harsh" has only Sharma left and stops being ambiguous.
    assigned: dict[str, tuple[uuid.UUID, float]] = {}
    while True:
        best_label, best_score = None, 0.0
        for label, scored in candidates.items():
            if label in assigned:
                continue
            free = [s for s in scored if s[1] not in taken]
            if free and free[0][0] > best_score:
                best_label, best_score = label, free[0][0]
        if best_label is None or best_score < AUTO_THRESHOLD:
            break
        free = [s for s in candidates[best_label] if s[1] not in taken]
        runner_up = free[1][0] if len(free) > 1 else 0.0
        if best_score - runner_up < AMBIGUITY_MARGIN:
            # Two plausible owners — a human call, or elimination's, not ours.
            # Mark handled so the loop can move on to unambiguous labels.
            assigned[best_label] = (None, 0.0)  # type: ignore[assignment]
            continue
        assigned[best_label] = (free[0][1], best_score)
        taken.add(free[0][1])

    # Drop the ambiguity placeholders before anyone reads `assigned`.
    assigned = {k: v for k, v in assigned.items() if v[0] is not None}

    # Elimination: exactly one speaker and one seat left, and they at least
    # vaguely resemble each other. With six people this closes most "joined
    # as a nickname" cases without a human.
    leftovers = [
        label for label in unmapped if label not in assigned and label not in bot_labels
    ]
    free_users = [uid for uid in roster if uid not in taken]
    if len(leftovers) == 1 and len(free_users) == 1:
        label, user_id = leftovers[0], free_users[0]
        score = score_candidate(label, roster[user_id], aliases.get(user_id, set()))
        if score >= ELIMINATION_FLOOR:
            assigned[label] = (user_id, score)
            taken.add(user_id)

    for label in labels:
        row = existing.get(label)
        if row is None:
            row = TranscriptSpeaker(transcript_id=transcript.id, speaker_label=label)
            db.add(row)
            existing[label] = row
        if row.resolved_via == "admin" or row.ignored:
            continue
        if label in bot_labels:
            row.ignored = True
            row.resolved_via = "auto"
            row.confidence = 1.0
        elif label in assigned:
            row.user_id, row.confidence = assigned[label]
            row.resolved_via = "auto"

    fully_resolved = all(s.user_id is not None or s.ignored for s in existing.values())
    transcript.status = (
        TranscriptStatus.RESOLVED if fully_resolved else TranscriptStatus.NEEDS_REVIEW
    )
    await db.flush()
    return fully_resolved


async def learn_aliases(db: AsyncSession, transcript: SessionTranscript) -> None:
    """Remember every confirmed label → user mapping, however it was decided.
    Next session, the same nickname resolves at alias strength."""
    result = await db.execute(
        select(TranscriptSpeaker).where(
            TranscriptSpeaker.transcript_id == transcript.id,
            TranscriptSpeaker.user_id.is_not(None),
        )
    )
    speakers = list(result.scalars())
    if not speakers:
        return

    known = {
        (a.user_id, a.display_name): a
        for a in (
            await db.execute(
                select(MeetAlias).where(MeetAlias.user_id.in_({s.user_id for s in speakers}))
            )
        ).scalars()
    }
    now = utc_now()
    for speaker in speakers:
        name = normalize(speaker.speaker_label)
        if not name:
            continue
        alias = known.get((speaker.user_id, name))
        if alias is None:
            alias = MeetAlias(user_id=speaker.user_id, display_name=name, last_seen_at=now)
            db.add(alias)
            known[(speaker.user_id, name)] = alias
        else:
            alias.last_seen_at = now
    await db.flush()


def speaker_metrics(
    sentences: list[dict], label_to_user: dict[str, uuid.UUID]
) -> dict[str, dict]:
    """Deterministic per-user numbers, keyed by ``str(user_id)``.

    Numbers the model is never asked to compute, because code gets them
    exactly right: seconds spoken, share of the room, turns taken, words,
    longest monologue, questions asked, filler words, and speaking pace.
    """
    per_user: dict[str, dict] = {}
    total_time = 0.0

    previous_user: str | None = None
    monologue_start: float | None = None

    for sentence in sentences:
        user_id = label_to_user.get(sentence.get("speaker", ""))
        if user_id is None:
            previous_user, monologue_start = None, None
            continue
        key = str(user_id)
        start, end = float(sentence.get("start", 0.0)), float(sentence.get("end", 0.0))
        duration = max(0.0, end - start)

        m = per_user.setdefault(
            key,
            {
                "talk_time_seconds": 0.0,
                "talk_share": 0.0,
                "turns": 0,
                "words": 0,
                "longest_monologue_seconds": 0.0,
                "questions_asked": 0,
                "first_spoke_at_seconds": start,
                "filler_words": {},
                "filler_total": 0,
            },
        )
        m["talk_time_seconds"] += duration
        text = sentence.get("text", "")
        m["words"] += len(text.split())
        if text.rstrip().endswith("?"):
            m["questions_asked"] += 1
        for phrase, n in count_fillers(text).items():
            m["filler_words"][phrase] = m["filler_words"].get(phrase, 0) + n
            m["filler_total"] += n
        total_time += duration

        if key != previous_user:
            m["turns"] += 1
            previous_user, monologue_start = key, start
        if monologue_start is not None:
            m["longest_monologue_seconds"] = max(
                m["longest_monologue_seconds"], end - monologue_start
            )

    for m in per_user.values():
        m["talk_time_seconds"] = round(m["talk_time_seconds"], 1)
        m["longest_monologue_seconds"] = round(m["longest_monologue_seconds"], 1)
        m["talk_share"] = round(m["talk_time_seconds"] / total_time, 3) if total_time else 0.0
        m["words_per_minute"] = (
            round(m["words"] / (m["talk_time_seconds"] / 60), 1)
            if m["talk_time_seconds"]
            else 0.0
        )

    return per_user

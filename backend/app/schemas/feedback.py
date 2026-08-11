from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class PeerTalk(BaseModel):
    """One bar in the talk-time graph. First names only, and the same list is
    in every report for the session — only ``is_you`` differs per reader."""

    name: str
    talk_time_seconds: float
    talk_share: float
    is_you: bool = False


class FeedbackMetrics(BaseModel):
    """The deterministic numbers, passed through as computed. All optional —
    a silent participant has (almost) empty metrics, and reports generated
    before a number existed simply don't have it."""

    talk_time_seconds: float | None = None
    talk_share: float | None = None
    turns: int | None = None
    words: int | None = None
    longest_monologue_seconds: float | None = None
    questions_asked: int | None = None
    words_per_minute: float | None = None
    #: Non-zero filler phrases only, e.g. ``{"like": 12, "you know": 4}``.
    filler_words: dict[str, int] | None = None
    filler_total: int | None = None
    #: Talk-time rank among the session's speaking learners, 1 = spoke most.
    rank: int | None = None
    peer_count: int | None = None
    peers: list[PeerTalk] | None = None


class LanguageNote(BaseModel):
    quote: str
    issue: str
    better: str
    #: One line on why fixing this matters. Empty on minor and pre-severity notes.
    why: str = ""
    #: "major" notes render up front; "minor" collapse behind a toggle. Reports
    #: generated before severity existed default to major so nothing is hidden.
    severity: str = "major"


class FeedbackStructured(BaseModel):
    """The model's answer as data — what the frontend renders section by
    section instead of parsing markdown. Mirrors the JSON schema in
    ``services/feedback.py``."""

    summary: str = ""
    strengths: list[str] = []
    areas_to_improve: list[str] = []
    language_notes: list[LanguageNote] = []
    collaboration: str = ""
    suggestions: list[str] = []


class GDScoreOut(BaseModel):
    """The learner-facing slice of the stored score. The model name and raw
    subscores stay server-side; ``rubric_version`` comes through so the
    frontend can refuse to draw a trend across scoring-rule boundaries."""

    composite: int | None = None
    pillars: dict[str, int] = {}
    rubric_version: int = 1


class FeedbackOut(ORMModel):
    id: uuid.UUID
    #: Denormalised for the dashboard list — which discussion this was.
    session_id: uuid.UUID
    session_slug: str
    session_title: str
    session_starts_at: datetime
    published_at: datetime
    report_md: str
    #: None for silent participants and pre-template reports — the frontend
    #: falls back to rendering ``report_md``.
    structured: FeedbackStructured | None
    metrics: FeedbackMetrics
    #: None for silent participants and reports scored before scores existed.
    score: GDScoreOut | None = None


# ------------------------------------------------- instructor / superuser view


class RosterUserOut(ORMModel):
    id: uuid.UUID
    full_name: str
    email: str


class SpeakerOut(ORMModel):
    id: uuid.UUID
    speaker_label: str
    user_id: uuid.UUID | None
    ignored: bool
    confidence: float | None
    resolved_via: str | None


class SpeakerMapIn(BaseModel):
    """Exactly one intent per call: map to a user, or mark ignored.
    ``user_id: null, ignored: false`` returns the row to "unresolved"."""

    user_id: uuid.UUID | None = None
    ignored: bool = False


class ManageReportOut(ORMModel):
    id: uuid.UUID
    learner: RosterUserOut
    status: str
    report_md: str
    published_at: datetime | None
    emailed_at: datetime | None


class ManageTranscriptSummary(ORMModel):
    id: uuid.UUID
    session_id: uuid.UUID
    session_title: str
    session_starts_at: datetime
    status: str
    duration_minutes: float | None
    unmatched_speakers: int
    published_reports: int
    total_reports: int


class ManageTranscriptDetail(ManageTranscriptSummary):
    speakers: list[SpeakerOut]
    #: Who the dropdown may offer: seated learners plus the instructor.
    roster: list[RosterUserOut]
    reports: list[ManageReportOut]

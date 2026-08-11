"""Scoring one learner's group-discussion performance, 0-100.

Five pillars — Content 30, Communication 20, Collaboration 20, Leadership 15,
Participation 15 — following what B-school GD panels actually weigh. Two kinds
of input, deliberately kept apart:

* **Deterministic subscores** computed here from transcript math: talk-share
  against an ideal band, turns spread across thirds, question rate, longest
  monologue, filler rate, speaking pace. These are stable across model
  versions and are what a learner's *trend* can safely be built on.
* **LLM rubric integers** (0-5, anchored) from the one structured feedback
  call in ``services/feedback.py``. These carry the judgment calls — content
  depth, genuine builds, initiation quality — but drift when the underlying
  model changes, so every stored score records ``rubric_version`` and the
  model name, and a version bump is the signal that trends cross a boundary.

Anti-gaming is structural, not detective: every countable behavior saturates
quickly (three good questions score the same as ten), quality gates sit in
front of every count (the rubric anchors award nothing for hollow name-drops
or unengaged statistics), and leadership credit is halved when participation
is outside a healthy band — hijacking the floor to "lead" earns nothing.

All constants live at the top: this file is the tuning surface.
"""

from __future__ import annotations

import uuid

from app.services.transcripts import count_fillers

RUBRIC_VERSION = 1

PILLAR_WEIGHTS = {
    "content": 0.30,
    "communication": 0.20,
    "collaboration": 0.20,
    "leadership": 0.15,
    "participation": 0.15,
}

#: Talk share relative to the ideal (1/N of learner-only talk time): full
#: credit inside 0.6-1.4x, fading to zero at 0.2x (near-silent) and 2.5x
#: (dominating the room).
SHARE_FULL = (0.6, 1.4)
SHARE_ZERO = (0.2, 2.5)

#: Sessions shorter than this don't get the thirds-spread subscore — the
#: thirds are too small to mean anything.
SPREAD_MIN_SESSION_SECONDS = 15 * 60

#: Questions per 10 minutes of session: full credit from 1 to the cap, no
#: extra credit beyond it (spamming questions buys nothing).
QUESTIONS_FULL_PER_10MIN = 1.0

#: Longest monologue: full credit up to 90s, zero from 150s.
MONOLOGUE_FULL_SECONDS = 90.0
MONOLOGUE_ZERO_SECONDS = 150.0

#: Fillers per 100 words: full credit up to 5, zero from 20.
FILLER_FULL_PER_100 = 5.0
FILLER_ZERO_PER_100 = 20.0

#: Speaking pace: full credit 110-170 wpm, fading to zero at 70 and 210.
WPM_FULL = (110.0, 170.0)
WPM_ZERO = (70.0, 210.0)

#: Leadership is halved when talk share is outside the widest healthy band —
#: neither the near-silent nor the floor-hog gets full leadership credit.
LEADERSHIP_GATE_FACTOR = 0.5

#: Subscore weights inside each pillar. Deterministic entries name a metric;
#: LLM entries name a 0-5 rubric dimension from the feedback call.
PARTICIPATION_WEIGHTS = {"talk_band": 40, "spread": 25, "questions": 20, "monologue": 15}
COMMUNICATION_WEIGHTS = {"filler": 25, "pace": 15, "clarity": 35, "vocabulary": 25}
CONTENT_WEIGHTS = {"facts_figures": 35, "examples_evidence": 25, "topic_relevance": 15, "depth": 25}
COLLABORATION_WEIGHTS = {"genuine_builds": 35, "listening": 30, "making_space": 35}
LEADERSHIP_WEIGHTS = {"initiation": 35, "conclusion": 35, "steering": 30}

#: The twelve LLM rubric dimensions, with the behavioral anchor the model is
#: scoring against. Shared with the JSON schema in ``services/feedback.py`` so
#: schema and scorer can never disagree about what exists.
LLM_RUBRIC_DIMENSIONS = {
    "clarity": "Sentences are easy to follow: one idea at a time, finished cleanly.",
    "vocabulary": "Word choice is accurate and natural; idioms used correctly.",
    "facts_figures": "Concrete facts, figures, or data that were relevant AND that "
    "the discussion engaged with. Sprinkled, unengaged statistics score 1, not 3.",
    "examples_evidence": "Real examples or evidence that support the argument.",
    "topic_relevance": "Contributions stay on the actual topic.",
    "depth": "Arguments are reasoned - because/therefore/trade-off - not bare assertion.",
    "genuine_builds": "References to peers that truly extend, qualify, or challenge "
    "their point. Hollow name-drops ('as X said' before an unrelated point) score 0.",
    "listening": "Replies actually address what the previous speaker said.",
    "making_space": "Leaves room for others: no interrupting or steamrolling, invites "
    "quieter members in.",
    "initiation": "Framed the topic clearly early in the discussion - structure, "
    "definition, or a map of the debate. Merely speaking first scores 0.",
    "conclusion": "Synthesized multiple viewpoints near the end. 'So yeah, that's "
    "all from my side' scores 0.",
    "steering": "Redirected drift, managed time, resolved clashes, kept the "
    "discussion moving.",
}


def _band(value: float, full: tuple[float, float], zero: tuple[float, float]) -> float:
    """1.0 inside [full], falling linearly to 0.0 at the zero bounds."""
    if full[0] <= value <= full[1]:
        return 1.0
    if value < full[0]:
        if value <= zero[0]:
            return 0.0
        return (value - zero[0]) / (full[0] - zero[0])
    if value >= zero[1]:
        return 0.0
    return (zero[1] - value) / (zero[1] - full[1])


def deterministic_subscores(
    sentences: list[dict],
    label_to_user: dict[str, uuid.UUID],
    learner_id: uuid.UUID,
    learner_ids: set[uuid.UUID],
) -> dict | None:
    """The transcript-math half of the score, all fractions 0-1.

    ``learner_ids`` is every learner who spoke; the instructor's time is
    excluded from the share baseline because outranking the host is not a
    fact about the learner. Returns None when the learner never spoke.
    """
    learner_talk: dict[uuid.UUID, float] = {}
    my_turn_starts: list[float] = []
    my_words = 0
    my_fillers = 0
    my_questions = 0
    my_longest = 0.0
    session_start: float | None = None
    session_end: float | None = None

    previous_user: uuid.UUID | None = None
    monologue_start: float | None = None

    for sentence in sentences:
        start = float(sentence.get("start", 0.0))
        end = float(sentence.get("end", 0.0))
        session_start = start if session_start is None else min(session_start, start)
        session_end = end if session_end is None else max(session_end, end)

        user_id = label_to_user.get(sentence.get("speaker", ""))
        if user_id is None:
            previous_user, monologue_start = None, None
            continue
        if user_id in learner_ids:
            learner_talk[user_id] = learner_talk.get(user_id, 0.0) + max(0.0, end - start)

        if user_id != previous_user:
            previous_user, monologue_start = user_id, start
            if user_id == learner_id:
                my_turn_starts.append(start)
        if user_id == learner_id:
            text = sentence.get("text", "")
            my_words += len(text.split())
            my_fillers += sum(count_fillers(text).values())
            if text.rstrip().endswith("?"):
                my_questions += 1
            if monologue_start is not None:
                my_longest = max(my_longest, end - monologue_start)

    my_talk = learner_talk.get(learner_id, 0.0)
    total_learner_talk = sum(learner_talk.values())
    if my_talk <= 0 or total_learner_talk <= 0 or session_start is None:
        return None

    session_seconds = max(0.0, (session_end or 0.0) - session_start)
    ideal = 1.0 / max(1, len(learner_ids))
    share_ratio = (my_talk / total_learner_talk) / ideal

    subs: dict[str, float | None] = {}
    subs["talk_band"] = _band(share_ratio, SHARE_FULL, SHARE_ZERO)

    if session_seconds >= SPREAD_MIN_SESSION_SECONDS:
        third = session_seconds / 3
        thirds_present = len(
            {
                min(2, int((t - session_start) / third)) if third else 0
                for t in my_turn_starts
            }
        )
        subs["spread"] = thirds_present / 3
    else:
        subs["spread"] = None  # not applicable; weight is redistributed

    q_rate = my_questions / (session_seconds / 600) if session_seconds else 0.0
    subs["questions"] = min(1.0, q_rate / QUESTIONS_FULL_PER_10MIN)

    if my_longest <= MONOLOGUE_FULL_SECONDS:
        subs["monologue"] = 1.0
    elif my_longest >= MONOLOGUE_ZERO_SECONDS:
        subs["monologue"] = 0.0
    else:
        subs["monologue"] = (MONOLOGUE_ZERO_SECONDS - my_longest) / (
            MONOLOGUE_ZERO_SECONDS - MONOLOGUE_FULL_SECONDS
        )

    fillers_per_100 = (my_fillers / my_words) * 100 if my_words else 0.0
    if fillers_per_100 <= FILLER_FULL_PER_100:
        subs["filler"] = 1.0
    elif fillers_per_100 >= FILLER_ZERO_PER_100:
        subs["filler"] = 0.0
    else:
        subs["filler"] = (FILLER_ZERO_PER_100 - fillers_per_100) / (
            FILLER_ZERO_PER_100 - FILLER_FULL_PER_100
        )

    wpm = my_words / (my_talk / 60) if my_talk else 0.0
    subs["pace"] = _band(wpm, WPM_FULL, WPM_ZERO)

    subs["share_ratio"] = round(share_ratio, 2)
    return subs


def _pillar(weights: dict[str, int], values: dict[str, float | None]) -> int | None:
    """Weighted 0-100 pillar score. Subscores that are None (not applicable)
    give their weight to the rest; an entirely-None pillar returns None."""
    earned, total = 0.0, 0
    for name, weight in weights.items():
        value = values.get(name)
        if value is None:
            continue
        earned += weight * value
        total += weight
    if total == 0:
        return None
    return round(100 * earned / total)


def compute_gd_score(deterministic: dict, rubric: dict | None, model: str) -> dict:
    """Combine deterministic subscores and the LLM rubric into pillar scores
    and the weighted composite. ``rubric`` may be None (model call fell back);
    LLM-only pillars are then absent and the composite reweights around them."""
    llm = {
        name: (rubric[name] / 5 if rubric and isinstance(rubric.get(name), (int, float)) else None)
        for name in LLM_RUBRIC_DIMENSIONS
    }

    pillars: dict[str, int | None] = {
        "participation": _pillar(PARTICIPATION_WEIGHTS, deterministic),
        "communication": _pillar(COMMUNICATION_WEIGHTS, {**deterministic, **llm}),
        "content": _pillar(CONTENT_WEIGHTS, llm),
        "collaboration": _pillar(COLLABORATION_WEIGHTS, llm),
        "leadership": _pillar(LEADERSHIP_WEIGHTS, llm),
    }

    share_ratio = deterministic.get("share_ratio")
    if pillars["leadership"] is not None and share_ratio is not None:
        if not (SHARE_ZERO[0] <= share_ratio <= SHARE_ZERO[1]):
            pillars["leadership"] = round(pillars["leadership"] * LEADERSHIP_GATE_FACTOR)

    earned, total = 0.0, 0.0
    for name, weight in PILLAR_WEIGHTS.items():
        if pillars[name] is None:
            continue
        earned += weight * pillars[name]
        total += weight
    composite = round(earned / total) if total else None

    return {
        "rubric_version": RUBRIC_VERSION,
        "model": model,
        "composite": composite,
        "pillars": {k: v for k, v in pillars.items() if v is not None},
        "deterministic": {
            k: (round(v, 3) if isinstance(v, float) else v)
            for k, v in deterministic.items()
            if v is not None
        },
        "llm_rubric": {k: rubric[k] for k in LLM_RUBRIC_DIMENSIONS if rubric and k in rubric},
    }

"""broad pillars

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-11

Narrow tracks out, broad pillars only. JAM, UPSC interview and Software & IT
each spoke to one audience; the tracks that remain — General, IELTS, Group
discussion, MBA, Visa interview, Corporate, Gen AI — are each a door many
kinds of people can walk through.

Topics are re-homed where they genuinely fit a pillar rather than deleted
wholesale:

- All of JAM's topics move to General. A JAM round *is* a general one-minute
  topic — the track was a format label, not a subject.
- "AI will replace programmers" moves to Gen AI, where it was always a
  better fit than Software & IT.
- "Women's safety in your city" moves to Group discussion — it is a staple
  GD topic, not a UPSC-only question.

Everything else in the three tracks is deleted; the movers take their new
track's ``sort_order`` so the chips stay in ranking order.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: text -> (new track, that track's sort_order). JAM is handled as a whole
#: track below; these are the two single-topic rescues.
_MOVES: dict[str, tuple[str, int]] = {
    "AI will replace programmers": ("Gen AI", 90),
    "Women's safety in your city": ("Group discussion", 40),
}

# What upgrade deletes, verbatim (track, category, text), so downgrade can
# put it back. JAM's rows are not here — they survive, re-homed.
_DELETED: list[tuple[str, str, str]] = [
    ("UPSC interview", "Interview classics", "Why civil services, honestly?"),
    ("UPSC interview", "Interview classics", "Your district's biggest problem"),
    ("UPSC interview", "Interview classics", "Defend your optional subject"),
    ("UPSC interview", "Interview classics", "A policy you would change tomorrow"),
    ("UPSC interview", "Interview classics", "Empathy or enforcement — a DM's dilemma"),
    ("UPSC interview", "Interview classics", "Your favourite leader's one flaw"),
    ("UPSC interview", "Interview classics", "First posting, and a flood hits"),
    ("UPSC interview", "Interview classics", "A bribe is offered on day one"),
    ("UPSC interview", "Interview classics", "Doubling farmers' income"),
    ("UPSC interview", "Hot takes", "Should civil servants be on social media?"),
    ("UPSC interview", "Hot takes", "Lateral entry into the IAS"),
    ("Software & IT", "Interview classics", "Explain an API to your grandmother"),
    ("Software & IT", "Interview classics", "Why did the deadline slip?"),
    ("Software & IT", "Interview classics", "Explain your project without jargon"),
    ("Software & IT", "Interview classics", "Walk me through a bug you fixed"),
    ("Software & IT", "Interview classics", "Explain tech debt to a manager"),
    ("Software & IT", "Interview classics", "Your favourite tool, and its worst flaw"),
    ("Software & IT", "Interview classics", "Convince me to rewrite nothing"),
    ("Software & IT", "Hot takes", "Remote standups are useless"),
    ("Software & IT", "Hot takes", "Tabs or spaces — defend your side"),
    ("Software & IT", "Hot takes", "Every engineer should do a support week"),
]

_JAM = "JAM (Just a Minute)"


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "UPDATE impromptu_topics SET track = 'General', sort_order = 10 WHERE track = :t"
        ),
        {"t": _JAM},
    )

    for text, (track, order) in _MOVES.items():
        conn.execute(
            sa.text(
                "UPDATE impromptu_topics SET track = :track, sort_order = :o WHERE text = :text"
            ),
            {"track": track, "o": order, "text": text},
        )

    conn.execute(
        sa.text(
            "DELETE FROM impromptu_topics WHERE track IN ('UPSC interview', 'Software & IT')"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "UPDATE impromptu_topics SET track = :t, sort_order = 30 "
            "WHERE track = 'General' AND text IN ('My first day at college', 'Life in a hostel', "
            "'The person behind my success', 'Street food beats restaurants', "
            "'Social media — boon or bane', 'Marks versus skills', 'Online classes beat classrooms', "
            "'Engineering is still worth it', 'Unity in diversity', 'Time is money', "
            "'If I were invisible for a day', 'The best mistake I ever made')"
        ),
        {"t": _JAM},
    )

    restore_order = {"UPSC interview": 50, "Software & IT": 100}
    for text, (_, _) in _MOVES.items():
        original = (
            "Software & IT" if text == "AI will replace programmers" else "UPSC interview"
        )
        conn.execute(
            sa.text(
                "UPDATE impromptu_topics SET track = :track, sort_order = :o WHERE text = :text"
            ),
            {"track": original, "o": restore_order[original], "text": text},
        )

    for track, category, text in _DELETED:
        conn.execute(
            sa.text(
                "INSERT INTO impromptu_topics (id, text, category, track, difficulty, is_active, sort_order) "
                "VALUES (:id, :text, :category, :track, NULL, TRUE, :o) "
                "ON CONFLICT (text) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "category": category,
                "track": track,
                "o": restore_order[track],
            },
        )

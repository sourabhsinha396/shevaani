"""impromptu tracks v2

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-11

Reshapes the impromptu topic bank around what people actually search for:

- ``sort_order`` — the popularity ranking, per track. The API orders by it
  and the frontend renders track chips in arrival order, so this column is
  the order on the page. Ranking (research, Aug 2026): IELTS speaking has
  the largest prep-search volume; JAM rounds are standard in Indian campus
  placements (TCS/Infosys/Accenture); group discussion feeds both MBA-PI
  and placements; the UPSC personality test is one of India's biggest
  interview-prep markets; Gen AI is the fastest-growing interview subject.
- Cabin crew removed — the narrowest audience of the original seed, cut in
  favour of the tracks above.
- Four new tracks seeded: JAM (Just a Minute), Group discussion,
  UPSC interview, Gen AI.
- Defensive trim of ``track``/``category`` so a value edited in sqladmin
  with a stray space cannot split a chip in two.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVERYDAY = "Everyday things"
ABSTRACT = "Big ideas"
OPINION = "Hot takes"
INTERVIEW = "Interview classics"

#: Lower renders first. Gaps of 10 so a track can be slotted in from sqladmin
#: without renumbering everything.
TRACK_ORDER: dict[str, int] = {
    "General": 10,
    "IELTS": 20,
    "JAM (Just a Minute)": 30,
    "Group discussion": 40,
    "UPSC interview": 50,
    "MBA": 60,
    "Visa interview": 70,
    "Corporate": 80,
    "Gen AI": 90,
    "Software & IT": 100,
}

# (track, category, [texts])
_NEW: list[tuple[str, str, list[str]]] = [
    (
        "JAM (Just a Minute)",
        EVERYDAY,
        [
            "My first day at college",
            "Life in a hostel",
            "The person behind my success",
            "Street food beats restaurants",
        ],
    ),
    (
        "JAM (Just a Minute)",
        OPINION,
        [
            "Social media — boon or bane",
            "Marks versus skills",
            "Online classes beat classrooms",
            "Engineering is still worth it",
        ],
    ),
    (
        "JAM (Just a Minute)",
        ABSTRACT,
        [
            "Unity in diversity",
            "Time is money",
            "If I were invisible for a day",
            "The best mistake I ever made",
        ],
    ),
    (
        "Group discussion",
        OPINION,
        [
            "Work from home is killing creativity",
            "India needs a four-day work week",
            "Cashless economy — dream or disaster?",
            "Should the railways be privatised?",
            "Influencers are the new teachers",
            "Startups versus stable jobs",
            "Degrees are losing their value",
            "Climate change — whose bill is it?",
            "Rural India runs urban India",
            "The English-medium obsession",
            "Reservation in private jobs",
            "One nation, one election",
        ],
    ),
    (
        "UPSC interview",
        INTERVIEW,
        [
            "Why civil services, honestly?",
            "Your district's biggest problem",
            "Defend your optional subject",
            "A policy you would change tomorrow",
            "Empathy or enforcement — a DM's dilemma",
            "Your favourite leader's one flaw",
            "First posting, and a flood hits",
            "A bribe is offered on day one",
            "Women's safety in your city",
            "Doubling farmers' income",
        ],
    ),
    (
        "UPSC interview",
        OPINION,
        [
            "Should civil servants be on social media?",
            "Lateral entry into the IAS",
        ],
    ),
    (
        "Gen AI",
        OPINION,
        [
            "AI will take your job — or your boss's",
            "ChatGPT wrote my homework — so what?",
            "Prompt engineering is not a real career",
            "AI will make us dumber",
            "Deepfakes will decide elections",
            "An AI doctor or a tired human doctor?",
        ],
    ),
    (
        "Gen AI",
        INTERVIEW,
        [
            "Explain ChatGPT to your grandmother",
            "Where do you use AI every day?",
            "Can AI be creative?",
            "What should schools do about AI?",
            "Build with AI or compete with it?",
            "If AI ran your city for a week",
        ],
    ),
]

# Kept verbatim from 0013 so downgrade can restore what upgrade deletes.
_CABIN_CREW: list[str] = [
    "Why do you want to fly?",
    "A passenger refuses to sit down",
    "Describe your idea of service",
    "Sell me the window seat",
    "A medical emergency mid-flight",
    "A time you stayed calm under pressure",
    "What makes a great first impression?",
    "Teamwork in a narrow aisle",
    "A difficult customer you won over",
    "Your favourite city to land in",
]


def upgrade() -> None:
    op.add_column(
        "impromptu_topics",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
    )

    conn = op.get_bind()

    # A track typed with a stray space in sqladmin renders as a second chip on
    # the tool. Trim first so the ranking below matches what is actually there.
    conn.execute(
        sa.text(
            "UPDATE impromptu_topics SET track = btrim(track), category = btrim(category)"
        )
    )

    conn.execute(sa.text("DELETE FROM impromptu_topics WHERE track = 'Cabin crew'"))

    rows = [
        {
            "id": str(uuid.uuid4()),
            "text": text,
            "category": category,
            "track": track,
            "sort_order": TRACK_ORDER[track],
        }
        for track, category, texts in _NEW
        for text in texts
    ]
    # Row-by-row with a conflict guard rather than bulk_insert: an operator may
    # already have hand-added one of these texts, and this migration losing a
    # race to sqladmin should not take the deploy down with it.
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO impromptu_topics (id, text, category, track, difficulty, is_active, sort_order) "
                "VALUES (:id, :text, :category, :track, NULL, TRUE, :sort_order) "
                "ON CONFLICT (text) DO NOTHING"
            ),
            row,
        )

    for track, order in TRACK_ORDER.items():
        conn.execute(
            sa.text("UPDATE impromptu_topics SET sort_order = :o WHERE track = :t"),
            {"o": order, "t": track},
        )


def downgrade() -> None:
    conn = op.get_bind()
    new_tracks = sorted({track for track, _, _ in _NEW})
    conn.execute(
        sa.text("DELETE FROM impromptu_topics WHERE track = ANY(:tracks)"),
        {"tracks": new_tracks},
    )
    for text in _CABIN_CREW:
        conn.execute(
            sa.text(
                "INSERT INTO impromptu_topics (id, text, category, track, difficulty, is_active) "
                "VALUES (:id, :text, :category, 'Cabin crew', NULL, TRUE) "
                "ON CONFLICT (text) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "text": text, "category": INTERVIEW},
        )
    op.drop_column("impromptu_topics", "sort_order")

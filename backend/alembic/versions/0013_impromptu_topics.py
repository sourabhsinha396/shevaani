"""impromptu topics

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-11

The free impromptu-speaking tool's topic bank, seeded.

Seeding lives in the migration rather than a CLI command because the tool is
public the moment it deploys: an empty bank would render a working timer with
nothing to say. ``category`` and ``track`` are display strings shown to
visitors verbatim — new verticals are added from sqladmin as rows, not here.

The seed list is duplicated from nothing: the frontend keeps its own small
fallback bank (for when the API is unreachable at render time), but this is
the canonical copy. The two are allowed to drift — the fallback only has to
be plausible, not complete.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVERYDAY = "Everyday things"
ABSTRACT = "Big ideas"
OPINION = "Hot takes"
INTERVIEW = "Interview classics"
CUE_CARD = "Cue cards"

# (track, category, [texts])
_SEED: list[tuple[str, str, list[str]]] = [
    (
        "General",
        EVERYDAY,
        [
            "Low tide",
            "The first rain",
            "Ceiling fans",
            "Street food",
            "Cutting chai",
            "Traffic jams",
            "Power cuts",
            "Local trains",
            "Sunday mornings",
            "House plants",
            "Umbrellas",
            "Standing in queues",
            "Auto-rickshaws",
            "Loose change",
            "Alarm clocks",
            "Wedding buffets",
            "Rooftops",
            "Gully cricket",
            "Old photographs",
            "Handwriting",
            "The window seat",
            "Mangoes",
            "School tiffin",
            "Barbershops",
            "Night markets",
            "Railway stations",
            "Your grandparents' house",
            "Flying kites",
            "Stray dogs",
            "Steel tumblers",
            "Bus conductors",
            "Shortcuts through lanes",
            "Pressure cookers",
            "Monsoon evenings",
            "Borrowed books",
            "Phone chargers",
            "Lift small talk",
            "Packing a suitcase",
        ],
    ),
    (
        "General",
        ABSTRACT,
        [
            "Courage",
            "Patience",
            "Luck",
            "Silence",
            "Nostalgia",
            "Ambition",
            "Boredom",
            "Curiosity",
            "Regret",
            "Discipline",
            "Jealousy",
            "Gratitude",
            "Failure",
            "Second chances",
            "Small talk",
            "White lies",
            "Overthinking",
            "Homesickness",
            "Beginnings",
            "Growing up",
            "Letting go",
            "Comfort zones",
            "Procrastination",
            "Peer pressure",
            "Self-doubt",
            "Kindness to strangers",
            "Waiting",
            "Being early",
            "Changing your mind",
        ],
    ),
    (
        "General",
        OPINION,
        [
            "Marks matter less than people think",
            "Everyone should live alone at least once",
            "Social media does more good than harm",
            "Homework should be abolished",
            "Small towns are better than big cities",
            "Money can buy happiness",
            "AI will create more jobs than it destroys",
            "Breakfast is overrated",
            "Group projects teach more than exams",
            "Everyone should learn to cook",
            "Work from home is here to stay",
            "Cricket gets too much attention in India",
            "Fluent English is not the same as intelligence",
            "College is not for everyone",
            "Board games beat video games",
            "It is okay to quit things",
            "Every student should take a gap year",
            "Cash is better than cards",
            "Winters are better than summers",
            "Reading the book beats watching the film",
        ],
    ),
    (
        "General",
        INTERVIEW,
        [
            "Tell me about a time you failed",
            "Describe yourself in three words",
            "Why should we pick you?",
            "A skill you taught yourself",
            "Your proudest moment",
            "A decision you would redo",
            "Where do you see yourself in five years?",
            "A time you disagreed with a senior",
            "Your biggest strength, with proof",
            "Explain your hobby like I'm five",
            "A lesson a mistake taught you",
            "The best advice you ever received",
            "A time you changed someone's mind",
            "What would your friends say about you?",
        ],
    ),
    (
        "MBA",
        INTERVIEW,
        [
            "Why MBA, why now?",
            "A business you admire, and why",
            "A time you led without authority",
            "Convince me your city needs one more startup",
            "Your favourite brand's biggest mistake",
            "A team conflict you resolved",
            "Sell me this pen, but honestly",
        ],
    ),
    (
        "MBA",
        OPINION,
        [
            "Leadership is overrated",
            "Ethics or profit — pick one",
            "GDP is a bad report card",
            "B-schools should drop entrance exams",
            "Family businesses beat startups",
        ],
    ),
    (
        "Cabin crew",
        INTERVIEW,
        [
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
        ],
    ),
    (
        "IELTS",
        CUE_CARD,
        [
            "Describe a person who inspires you",
            "A place you would like to revisit",
            "A gift you still remember",
            "A skill you want to learn",
            "A book that stayed with you",
            "An important decision you made",
            "A festival you enjoy",
            "Something you own that matters to you",
            "A time you helped a stranger",
            "Your favourite part of the day",
            "A website you use often",
            "A time you were pleasantly surprised",
        ],
    ),
    (
        "Visa interview",
        INTERVIEW,
        [
            "Why this country?",
            "Why this university?",
            "Who is funding your studies?",
            "What will you do after graduating?",
            "Why not study this at home?",
            "What ties bring you back home?",
            "How did you choose your course?",
            "Your plans if the visa is refused",
            "Your career five years after the degree",
            "What does your sponsor do?",
        ],
    ),
    (
        "Corporate",
        EVERYDAY,
        [
            "Meetings that should have been emails",
            "Small talk before the call starts",
            "The office lunch table",
            "Monday mornings",
            "Working late",
        ],
    ),
    (
        "Corporate",
        INTERVIEW,
        [
            "Introduce yourself to a new client",
            "Deliver bad news to a stakeholder",
            "Explain a delay without excuses",
            "Ask for a raise",
            "Tell your manager they are wrong, nicely",
            "Present a quarterly result in one minute",
            "Give feedback to someone senior",
        ],
    ),
    (
        "Corporate",
        OPINION,
        [
            "Office politics — play or stay out?",
            "Open offices were a mistake",
            "Job hopping is smart",
        ],
    ),
    (
        "Software & IT",
        INTERVIEW,
        [
            "Explain an API to your grandmother",
            "Why did the deadline slip?",
            "Explain your project without jargon",
            "Walk me through a bug you fixed",
            "Explain tech debt to a manager",
            "Your favourite tool, and its worst flaw",
            "Convince me to rewrite nothing",
        ],
    ),
    (
        "Software & IT",
        OPINION,
        [
            "AI will replace programmers",
            "Remote standups are useless",
            "Tabs or spaces — defend your side",
            "Every engineer should do a support week",
        ],
    ),
]


def upgrade() -> None:
    table = op.create_table(
        "impromptu_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.String(200), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("track", sa.String(60), nullable=False),
        sa.Column("difficulty", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_impromptu_topics"),
        sa.UniqueConstraint("text", name="uq_impromptu_topics_text"),
    )
    op.create_index("ix_impromptu_topics_category", "impromptu_topics", ["category"])
    op.create_index("ix_impromptu_topics_track", "impromptu_topics", ["track"])

    op.bulk_insert(
        table,
        [
            {
                "id": uuid.uuid4(),
                "text": text,
                "category": category,
                "track": track,
                "difficulty": None,
                "is_active": True,
            }
            for track, category, texts in _SEED
            for text in texts
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_impromptu_topics_track", table_name="impromptu_topics")
    op.drop_index("ix_impromptu_topics_category", table_name="impromptu_topics")
    op.drop_table("impromptu_topics")

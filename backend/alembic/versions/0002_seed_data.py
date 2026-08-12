"""seed data

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12

Everything the app expects to find in a fresh database:

- the ``site_settings`` singleton row (the table's check constraint pins
  ``id = 1``; the app reads it, never creates it),
- the impromptu tool's topic bank - the tool is public the moment it
  deploys, and an empty bank would render a working timer with nothing to
  say. Three broad tracks: General, Group discussion, Gen AI. New topics
  and tracks are added from sqladmin as rows, not here.

Credit packs and the superuser are seeded by CLI commands (``make packs``,
``make superuser``), not migrations - they carry environment-specific values.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (track, sort_order, category, [texts]). ``sort_order`` ranks the track
#: chips on the page - lower renders first, gaps of 10 so a new track can be
#: slotted in from sqladmin without renumbering everything.
_TOPICS: list[tuple[str, int, str, list[str]]] = [
    ("General", 10, "Big ideas", [
        "Ambition",
        "Beginnings",
        "Being early",
        "Boredom",
        "Changing your mind",
        "Comfort zones",
        "Courage",
        "Curiosity",
        "Discipline",
        "Failure",
        "Gratitude",
        "Growing up",
        "Homesickness",
        "If I were invisible for a day",
        "Jealousy",
        "Kindness to strangers",
        "Letting go",
        "Luck",
        "Nostalgia",
        "Overthinking",
        "Patience",
        "Peer pressure",
        "Procrastination",
        "Regret",
        "Second chances",
        "Self-doubt",
        "Silence",
        "Small talk",
        "The best mistake I ever made",
        "Time is money",
        "Unity in diversity",
        "Waiting",
        "White lies",
    ]),
    ("General", 10, "Everyday things", [
        "Alarm clocks",
        "Auto-rickshaws",
        "Barbershops",
        "Borrowed books",
        "Bus conductors",
        "Ceiling fans",
        "Cutting chai",
        "Flying kites",
        "Gully cricket",
        "Handwriting",
        "House plants",
        "Life in a hostel",
        "Lift small talk",
        "Local trains",
        "Loose change",
        "Low tide",
        "Mangoes",
        "Monsoon evenings",
        "My first day at college",
        "Night markets",
        "Old photographs",
        "Packing a suitcase",
        "Phone chargers",
        "Power cuts",
        "Pressure cookers",
        "Railway stations",
        "Rooftops",
        "School tiffin",
        "Shortcuts through lanes",
        "Standing in queues",
        "Steel tumblers",
        "Stray dogs",
        "Street food",
        "Street food beats restaurants",
        "Sunday mornings",
        "The first rain",
        "The person behind my success",
        "The window seat",
        "Traffic jams",
        "Umbrellas",
        "Wedding buffets",
        "Your grandparents' house",
    ]),
    ("General", 10, "Hot takes", [
        "AI will create more jobs than it destroys",
        "Board games beat video games",
        "Breakfast is overrated",
        "Cash is better than cards",
        "College is not for everyone",
        "Cricket gets too much attention in India",
        "Engineering is still worth it",
        "Every student should take a gap year",
        "Everyone should learn to cook",
        "Everyone should live alone at least once",
        "Fluent English is not the same as intelligence",
        "Group projects teach more than exams",
        "Homework should be abolished",
        "It is okay to quit things",
        "Marks matter less than people think",
        "Marks versus skills",
        "Money can buy happiness",
        "Online classes beat classrooms",
        "Reading the book beats watching the film",
        "Small towns are better than big cities",
        "Social media does more good than harm",
        "Social media — boon or bane",
        "Winters are better than summers",
        "Work from home is here to stay",
    ]),
    ("General", 10, "Interview classics", [
        "A decision you would redo",
        "A lesson a mistake taught you",
        "A skill you taught yourself",
        "A time you changed someone's mind",
        "A time you disagreed with a senior",
        "Describe yourself in three words",
        "Explain your hobby like I'm five",
        "Tell me about a time you failed",
        "The best advice you ever received",
        "What would your friends say about you?",
        "Where do you see yourself in five years?",
        "Why should we pick you?",
        "Your biggest strength, with proof",
        "Your proudest moment",
    ]),
    ("Group discussion", 40, "Hot takes", [
        "Cashless economy — dream or disaster?",
        "Climate change — whose bill is it?",
        "Degrees are losing their value",
        "India needs a four-day work week",
        "Influencers are the new teachers",
        "One nation, one election",
        "Reservation in private jobs",
        "Rural India runs urban India",
        "Should the railways be privatised?",
        "Startups versus stable jobs",
        "The English-medium obsession",
        "Work from home is killing creativity",
    ]),
    ("Group discussion", 40, "Interview classics", [
        "Women's safety in your city",
    ]),
    ("Gen AI", 90, "Hot takes", [
        "AI will make us dumber",
        "AI will replace programmers",
        "AI will take your job — or your boss's",
        "An AI doctor or a tired human doctor?",
        "ChatGPT wrote my homework — so what?",
        "Deepfakes will decide elections",
        "Prompt engineering is not a real career",
    ]),
    ("Gen AI", 90, "Interview classics", [
        "Build with AI or compete with it?",
        "Can AI be creative?",
        "Cosine similarity, in plain words",
        "Explain ChatGPT to your grandmother",
        "Explain attention to a five-year-old",
        "How does an LLM actually work?",
        "If AI ran your city for a week",
        "Open weights versus closed models",
        "RAG or fine-tuning — when and why?",
        "Temperature — same question, different answers",
        "Tokens — why AI reads in chunks",
        "Vector databases in one minute",
        "What is a context window?",
        "What is an embedding, really?",
        "What is prompt injection?",
        "What should schools do about AI?",
        "Where do you use AI every day?",
        "Why are GPUs the currency of AI?",
        "Why do chatbots hallucinate?",
    ]),
]


def upgrade() -> None:
    conn = op.get_bind()

    op.execute("INSERT INTO site_settings (id) VALUES (1)")

    for track, sort_order, category, texts in _TOPICS:
        for text in texts:
            conn.execute(
                sa.text(
                    "INSERT INTO impromptu_topics (id, text, category, track, difficulty, is_active, sort_order) "
                    "VALUES (:id, :text, :category, :track, NULL, TRUE, :o)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "text": text,
                    "category": category,
                    "track": track,
                    "o": sort_order,
                },
            )


def downgrade() -> None:
    op.execute("DELETE FROM impromptu_topics")
    op.execute("DELETE FROM site_settings")

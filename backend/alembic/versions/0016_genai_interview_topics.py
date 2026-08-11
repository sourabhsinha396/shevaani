"""gen ai interview topics

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-11

Deepens Gen AI's "Interview classics" with the technical-explainer prompts
real interviews (and good short videos) are made of: how LLMs work,
embeddings, cosine similarity, RAG, hallucination. Phrased as things a
person can say out loud for a minute — "Cosine similarity, in plain words" —
not as quiz questions with a single right answer.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTERVIEW = "Interview classics"
_TRACK = "Gen AI"
_SORT = 90  # Gen AI's slot from 0014

_TOPICS: list[str] = [
    "How does an LLM actually work?",
    "What is an embedding, really?",
    "Cosine similarity, in plain words",
    "Why do chatbots hallucinate?",
    "Tokens — why AI reads in chunks",
    "RAG or fine-tuning — when and why?",
    "What is a context window?",
    "Temperature — same question, different answers",
    "Vector databases in one minute",
    "Explain attention to a five-year-old",
    "What is prompt injection?",
    "Open weights versus closed models",
    "Why are GPUs the currency of AI?",
]


def upgrade() -> None:
    conn = op.get_bind()
    for text in _TOPICS:
        conn.execute(
            sa.text(
                "INSERT INTO impromptu_topics (id, text, category, track, difficulty, is_active, sort_order) "
                "VALUES (:id, :text, :category, :track, NULL, TRUE, :o) "
                "ON CONFLICT (text) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "category": INTERVIEW,
                "track": _TRACK,
                "o": _SORT,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM impromptu_topics WHERE text = ANY(:texts)"),
        {"texts": _TOPICS},
    )

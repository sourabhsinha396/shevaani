"""Human-readable session slugs.

A slug is what the URL says instead of a UUID: ``/discussions/tuesday-debate-
club`` rather than ``/discussions/2e945ef2-…``. The slug is derived from the
title once, at creation, and then owned by the row — retitling a session does
not move its URL out from under everyone who shared it.

Uniqueness is global across the table (the column is unique), so recurring
sessions with the same title get a numbered suffix: ``tuesday-debate-club``,
``tuesday-debate-club-2``, and so on.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session

#: Leaves head-room under the 250-char column for a ``-NN`` suffix.
_MAX_BASE_LENGTH = 240


def slugify(text: str) -> str:
    """Lowercase, ASCII-ish, hyphen-separated. Empty input (a title that is all
    punctuation) falls back to ``session`` rather than an empty slug, which the
    router would read as a different path entirely."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:_MAX_BASE_LENGTH].rstrip("-") or "session"


async def unique_session_slug(
    db: AsyncSession,
    title: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> str:
    """The slug this title gets: the plain form if free, else first free
    ``-N``. One query — the taken set is small even years in."""
    base = slugify(title)
    query = select(Session.slug).where(Session.slug.like(f"{base}%"))
    if exclude_id is not None:
        query = query.where(Session.id != exclude_id)
    taken = set((await db.execute(query)).scalars())

    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"

"""Free public tools — currently just the impromptu-speaking topic bank.

Unauthenticated and read-only. The whole bank ships in one response rather
than a random-topic endpoint, because shuffling client-side makes every
"new topic" click instant and lets the frontend derive its filter chips from
the data it already has. At a few hundred short rows the payload is smaller
than the page's hero image, and the frontend holds it for the length of its
ISR window anyway.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.impromptu import ImpromptuTopic
from app.schemas.tools import ImpromptuTopicOut

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/impromptu/topics", response_model=list[ImpromptuTopicOut])
async def impromptu_topics(db: DbSession) -> list[ImpromptuTopicOut]:
    """Every active topic. Filtering is the client's job — see module docstring."""
    result = await db.execute(
        select(ImpromptuTopic)
        .where(ImpromptuTopic.is_active.is_(True))
        # `sort_order` first — the client renders track chips in arrival
        # order, so this line IS the popularity ranking on the page. The rest
        # keeps the response stable byte-for-byte for caching.
        .order_by(
            ImpromptuTopic.sort_order,
            ImpromptuTopic.track,
            ImpromptuTopic.category,
            ImpromptuTopic.text,
        )
    )
    return [
        ImpromptuTopicOut(
            text=row.text,
            category=row.category,
            track=row.track,
            difficulty=row.difficulty,
        )
        for row in result.scalars()
    ]

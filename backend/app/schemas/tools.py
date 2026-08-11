from __future__ import annotations

from pydantic import BaseModel


class ImpromptuTopicOut(BaseModel):
    """One prompt, public by design — there is nothing else on the row worth
    hiding, and ids would only invite the frontend to build state around them."""

    text: str
    category: str
    track: str
    difficulty: str | None = None

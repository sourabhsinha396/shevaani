"""Enqueue side of ARQ, used by the API.

Jobs are always enqueued **after** the transaction commits. Enqueuing inside a
transaction risks a worker picking up a job for a row that was then rolled back.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue(job: str, *args: Any, **kwargs: Any) -> None:
    """Fire-and-forget. A queue hiccup must never fail a request that already
    committed — the retry_pending_meetings cron is the safety net."""
    try:
        pool = await get_pool()
        await pool.enqueue_job(job, *args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to enqueue %s", job)

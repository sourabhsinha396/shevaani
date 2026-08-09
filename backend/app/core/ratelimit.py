"""Rate limiting, on Redis.

Redis rather than in-process counters because there is more than one API worker
and an in-process limit is really "N times the limit, and no limit at all after
a restart". Redis is already in the stack for ARQ, so this adds no infrastructure.

**The endpoint this exists for** is ``GET /sessions/{id}/join``. It returns a
Meet join URL, which is a bearer credential — anyone holding it can walk into a
paid session. It is already gated on enrollment and the time window, and every
access is logged, but logging an enumeration attempt is not the same as stopping
one. Everything else here is ordinary hygiene by comparison.

**Fixed windows, not a sliding log.** A fixed window lets through up to twice the
limit across a window boundary. The alternative costs a sorted set per identity
and a cleanup story, and the thing being defended against — scripted enumeration,
credential stuffing, someone holding seats — does not care about a factor of two.
It cares about the difference between 10 a minute and 10,000.

**Failure is open, deliberately.** If Redis is unreachable the request is allowed
and the failure is logged loudly. Failing closed would mean a Redis blip locks
every learner out of a session they paid for, which is a worse outcome than a few
unthrottled minutes — and a Redis outage is already visible, because the worker
stops with it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Request

from app.core.config import settings
from app.workers import queue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Limit:
    """``times`` requests per ``seconds``."""

    times: int
    seconds: int

    def __str__(self) -> str:
        return f"{self.times}/{self.seconds}s"


# The numbers. Grouped here rather than spread across the routes so the whole
# policy can be read — and argued with — in one place.

#: Wrong passwords are cheap to try and the account is the prize. Ten a minute
#: is far above what a person who has forgotten theirs will do, and far below
#: what a list of leaked credentials needs to be useful.
LOGIN = Limit(10, 60)

#: Signup is where fake accounts come from, and there is no legitimate reason to
#: create three in a minute from one address.
REGISTER = Limit(3, 60)

#: Each one sends an email to somebody else's inbox. The limit is as much about
#: not being a spam cannon as it is about protecting us.
FORGOT_PASSWORD = Limit(3, 60)
VERIFY_EMAIL_SEND = Limit(3, 300)

#: Tight on purpose. A learner opens the join link once, maybe three times if the
#: first attempt goes wrong. Anything past that is a script.
JOIN = Limit(10, 60)
#: The per-IP twin of the above, wider because a household or an office shares
#: one address, and narrow enough that enumerating sessions is hopeless.
JOIN_PER_IP = Limit(30, 60)

#: A script holding seats across every published session is the abuse here, not
#: someone booking two discussions in an evening.
BOOKING = Limit(12, 60)

#: Opening checkout sessions costs money at the provider and clutters their
#: dashboard, and nobody buys credits six times a minute.
CHECKOUT = Limit(6, 60)

#: Unauthenticated and free to send, so it is worth a limit even though the
#: messages land in a table rather than an inbox.
CONTACT = Limit(5, 300)


def client_ip(request: Request) -> str:
    """The caller's address, as far as we are willing to believe it.

    ``X-Forwarded-For`` is caller-supplied and trivially spoofed, so it is only
    read when the deployment says it sits behind a proxy that overwrites it.
    Trusting it by default would make every per-IP limit here opt-out: send a
    different header each time and there is no limit at all.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def consume(bucket: str, identity: str, limit: Limit) -> int | None:
    """Count one request. Returns seconds to wait if the limit is spent, else None."""
    if not settings.rate_limit_enabled:
        return None

    key = f"ratelimit:{bucket}:{identity}"
    try:
        redis = await queue.get_pool()
        pipeline = redis.pipeline()
        pipeline.incr(key)
        # Only on the first hit of a window, so a burst cannot keep pushing the
        # expiry out and turn a 60-second window into a permanent block.
        pipeline.expire(key, limit.seconds, nx=True)
        count, _ = await pipeline.execute()
        if int(count) <= limit.times:
            return None
        ttl = await redis.ttl(key)
    except Exception:  # noqa: BLE001 — see the module docstring: fail open.
        logger.exception("Rate limiter unavailable; allowing %s for %s", bucket, identity)
        return None

    return max(int(ttl), 1)

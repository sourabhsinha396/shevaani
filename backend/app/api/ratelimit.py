"""The route-facing half of rate limiting.

The counter and the policy numbers live in :mod:`app.core.ratelimit`, which knows
nothing about HTTP. This is the part that turns "you are over the limit" into a
429 with a ``Retry-After`` the frontend can act on, and it lives in the API layer
because that is the only layer that should be importing authentication.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from app.api.deps import OptionalUser
from app.core.ratelimit import Limit, client_ip, consume

logger = logging.getLogger(__name__)


def limiter(bucket: str, limit: Limit, *, per_ip: Limit | None = None):
    """Build a dependency that throttles a route.

    Identity is the signed-in user when there is one, and the IP otherwise — a
    shared office address should not be able to lock out everyone behind it just
    because one person is signed in and misbehaving. ``per_ip`` adds a second,
    wider bucket that applies regardless, which is what stops an attacker
    cycling through accounts to stay under the per-user limit.
    """

    async def dependency(request: Request, user: OptionalUser) -> None:
        checks: list[tuple[str, str, Limit]] = []
        if user is not None:
            checks.append((bucket, f"user:{user.id}", limit))
        else:
            checks.append((bucket, f"ip:{client_ip(request)}", limit))
        if per_ip is not None:
            checks.append((f"{bucket}:ip", f"ip:{client_ip(request)}", per_ip))

        for name, identity, rule in checks:
            retry_after = await consume(name, identity, rule)
            if retry_after is not None:
                logger.info("Rate limited %s on %s (%s)", identity, name, rule)
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "That's a lot of requests. Give it a moment and try again.",
                    headers={"Retry-After": str(retry_after)},
                )

    return dependency

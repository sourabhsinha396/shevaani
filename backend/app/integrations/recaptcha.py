"""Server-side check of the reCAPTCHA v2 checkbox.

The widget on the login, registration and forgot-password forms hands the
browser a one-time token; the only proof it is genuine is asking Google's
``siteverify`` endpoint, which is what this does. The token is spent by the
ask — a retry needs a fresh tick of the checkbox, which is why the frontend
resets the widget whenever a submit fails.

Unlike Slack, this *does* run on the request path: the whole point is to stand
between a bot and the endpoint. Two consequences:

**Unset secret means skipped, not broken.** Local development and tests run
with no Google account, exactly like email and object storage.

**Google being down fails open.** If ``siteverify`` cannot be reached, the
request goes through and the failure is logged. A captcha outage that locks
every learner out of signing in costs more than the bots it would have caught
in the window — and the per-IP rate limits on these endpoints still stand.
An *invalid* token, by contrast, is always a refusal.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def verify(token: str | None, *, ip: str | None = None) -> bool:
    """Whether the request may proceed. Never raises."""
    if not settings.recaptcha_configured:
        return True
    if not token:
        return False
    data = {"secret": settings.recaptcha_secret_key, "response": token}
    if ip:
        data["remoteip"] = ip
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(_VERIFY_URL, data=data)
            response.raise_for_status()
            return bool(response.json().get("success"))
    except httpx.HTTPError:
        logger.exception("recaptcha siteverify unreachable; failing open")
        return True


async def require(token: str | None, request: Request) -> None:
    """Refuse the request unless the captcha passes (or is not configured).

    Called first thing, before any database work, by every anonymous write
    endpoint a bot would hammer: register, login, forgot-password, contact.
    A refusal is a 400, not a 401 — nothing about the caller has been judged
    except the checkbox.
    """
    ok = await verify(token, ip=request.client.host if request.client else None)
    if not ok:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Please tick the “I'm not a robot” box and try again.",
        )

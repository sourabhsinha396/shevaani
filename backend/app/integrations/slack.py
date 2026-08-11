"""Operational notifications to Slack.

Superusers should find out that a session auto-cancelled or that a Meet link
failed without sitting in the admin refreshing it. That is all this is: a
notification channel, never a system of record. Everything it reports is already
a row in the database — the message is a nudge towards the row, not the row.

Three rules follow from that, and they are the whole design:

**It never runs on the request path.** :func:`dispatch` only enqueues; the worker
calls :func:`deliver`. Slack being down, slow, or rate-limiting must not be able
to fail a signup or a payment.

**It never raises.** A failed post is logged and swallowed. Notifications are
allowed to be lost; the thing they describe is not.

**It never carries a secret or a learner's address.** Join URLs are bearer
credentials — anyone in the channel holding one can walk into a paid session —
and Slack history is searchable, exportable, and often wider than the people who
should see learner emails. Messages name *what happened* and enough to find the
row: a session title, a payment amount, a user id. Not an inbox, not a link.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.workers import queue

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

def _prefix() -> str:
    """Tag every message with the environment unless it is production.

    A shared channel where staging noise is indistinguishable from production
    noise is how real alerts start being ignored.
    """
    return "" if settings.environment.lower() == "production" else f"[{settings.environment}] "


async def dispatch(text: str) -> None:
    """Ask for a message to be posted. Safe to call from anywhere, including a
    request handler — it does no network I/O of its own."""
    if not settings.slack_configured:
        logger.debug("slack not configured, dropping: %s", text)
        return
    await queue.enqueue("post_slack_message", text)


async def deliver(text: str) -> bool:
    """Actually post. Worker-only. Returns whether Slack accepted it."""
    if not settings.slack_configured:
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                settings.slack_webhook_url, json={"text": f"{_prefix()}{text}"}
            )
    except httpx.HTTPError as exc:
        logger.warning("Slack post failed: %s", exc)
        return False

    if not response.is_success:
        # Includes the body: Slack returns "invalid_token" / "channel_not_found"
        # as plain text, which is the difference between a broken webhook and a
        # transient blip.
        logger.warning(
            "Slack rejected the message (%s): %s", response.status_code, response.text[:200]
        )
        return False
    return True


# ---------------------------------------------------------------- messages
#
# Builders rather than call-site f-strings, so what goes to Slack is reviewable
# in one place — which is also where the "no emails, no join URLs" rule is kept
# honest.


def signup(*, full_name: str, country: str | None) -> str:
    where = f" from {country.upper()}" if country else ""
    return f":wave: New learner: *{full_name}*{where}."


def contact_message(*, name: str, subject: str) -> str:
    """A support nudge without copying private contact-form contents to Slack."""
    return f":email: New contact message from *{name}*: {subject}"


def payment_succeeded(*, amount_minor: int, currency: str, credits: int, provider: str) -> str:
    return (
        f":moneybag: Payment received — {_money(amount_minor, currency)} "
        f"for {credits} credit(s) via {provider}."
    )


def session_auto_cancelled(*, title: str, seats_taken: int, min_seats: int, learners: int) -> str:
    return (
        f":no_entry_sign: Auto-cancelled *{title}* — {seats_taken} of {min_seats} seats. "
        f"{learners} learner(s) refunded and notified."
    )


def meeting_failed(*, title: str, session_id: str, error: str) -> str:
    """The one thing in the system that can fail quietly (PLAN, third-party
    isolation). This is how it stops being quiet."""
    return (
        f":rotating_light: No Meet link for *{title}* (`{session_id}`) after repeated "
        f"attempts. The session is intact; learners cannot join until it is fixed.\n"
        f"> {error[:300]}"
    )


def webhook_signature_failed(*, provider: str, reason: str) -> str:
    return (
        f":closed_lock_with_key: Rejected a {provider} webhook: {reason}. "
        f"Either the secret is wrong or someone is posting forged events."
    )


def google_connection_lost(*, full_name: str, reason: str) -> str:
    """An instructor's Google grant died. Every session they host is now
    unhostable until they reconnect, so this is not a quiet housekeeping event."""
    return (
        f":link: *{full_name}*'s Google connection has been retired and their "
        f"sessions can no longer get a Meet link until they reconnect.\n"
        f"> {reason[:300]}"
    )


def backup_failed(*, error: str) -> str:
    return f":floppy_disk: Nightly database backup failed.\n> {error[:300]}"


#: A$ rather than $ for AUD: this reads alongside USD amounts in the same
#: channel, and two different currencies sharing one symbol is exactly the kind
#: of ambiguity a money notification should not have.
_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AUD": "A$"}


def _money(amount_minor: int, currency: str) -> str:
    symbol = _SYMBOLS.get(currency.upper(), f"{currency.upper()} ")
    return f"{symbol}{amount_minor / 100:,.2f}"

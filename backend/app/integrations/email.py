"""Outbound email, over Brevo.

Two seams, and the difference between them is the whole module:

* :func:`dispatch` — "this message should go out". Enqueues and returns. Safe to
  call from a request handler, which is where most of these originate.
* :func:`deliver` — actually talks to Brevo. Called by the worker job and by
  nothing else.

Sending on the request path is the failure mode this exists to prevent: a slow
provider would turn every signup into a slow signup, and a provider outage would
turn a password reset into a 500 that also tells the caller whether the address
exists. Neither is acceptable, and neither is recoverable by adding a timeout.

With no API key configured, :func:`deliver` logs the message in full and returns
False. In development that log **is** the inbox — a reset link nobody can read
makes the flow untestable — so it prints the body rather than a summary.

Nothing here raises. A message that cannot be sent is a message that was not
sent; it is never an error the caller has to handle, because there is nothing
useful any caller could do about it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.workers import queue

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    #: Shown instead of the raw address in the recipient's client.
    to_name: str | None = None


async def dispatch(message: Email) -> None:
    """Hand a message to the worker. Does no network I/O.

    Unlike the meeting jobs, this may be enqueued before the caller's transaction
    commits. The message is built complete here and the worker reads nothing back
    from the database, so a worker that runs first cannot see a half-written row —
    the worst case is an email about a transaction that then rolled back, which
    for a reset link means a link that simply does not work.
    """
    await queue.enqueue(
        "send_email",
        message.to,
        message.subject,
        message.body,
        message.to_name,
    )


async def deliver(message: Email) -> bool:
    """Send one message. Returns whether it actually went anywhere. Worker-only."""
    if not settings.email_configured:
        logger.info(
            "email suppressed (no provider configured)\nto: %s\nsubject: %s\n\n%s",
            message.to,
            message.subject,
            message.body,
        )
        return False

    payload = {
        "sender": {"name": settings.email_from_name, "email": settings.email_from},
        "to": [{"email": message.to, **({"name": message.to_name} if message.to_name else {})}],
        "subject": message.subject,
        "textContent": message.body,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                BREVO_ENDPOINT,
                headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.warning("Brevo request failed for %s: %s", message.to, exc)
        return False

    if not response.is_success:
        # Brevo answers with a JSON {code, message}; the code is the difference
        # between "your key is wrong" and "that address is on the blocklist",
        # and only one of those is worth waking someone up for.
        logger.warning(
            "Brevo rejected a message to %s (%s): %s",
            message.to,
            response.status_code,
            response.text[:300],
        )
        return False
    return True


# ------------------------------------------------------------------ helpers


def _local(when: datetime, timezone: str | None) -> str:
    """Render a UTC instant in the reader's own timezone.

    Every learner has one on their profile and it is the only sensible frame for
    "your session starts at" — a reminder in UTC is a reminder somebody has to
    do arithmetic on at 6am. Falls back to the platform timezone if the stored
    name is unusable.
    """
    try:
        tz = ZoneInfo(timezone) if timezone else settings.tz
    except Exception:  # noqa: BLE001 — a bad tz name must not lose the email
        tz = settings.tz
    return f"{when.astimezone(tz):%A %d %B, %H:%M} ({tz.key})"


#: A$ rather than $ for AUD — a receipt is the last place to leave which dollar
#: was charged open to interpretation.
_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AUD": "A$"}


def _money(amount_minor: int, currency: str) -> str:
    symbol = _SYMBOLS.get(currency.upper(), f"{currency.upper()} ")
    return f"{symbol}{amount_minor / 100:,.2f}"


def _sign_off(body: str) -> str:
    return f"{body}\n\n— Shevaani"


# ------------------------------------------------------------------ account


def password_reset_url(token: str) -> str:
    return f"{settings.frontend_origin}/reset-password?token={quote(token)}"


def build_password_reset(*, to: str, full_name: str, token: str) -> Email:
    url = password_reset_url(token)
    minutes = settings.password_reset_ttl_minutes
    return Email(
        to=to,
        to_name=full_name,
        subject="Reset your Shevaani password",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            "Someone asked to reset the password on this account. If that was you, "
            f"open the link below within {minutes} minutes:\n\n"
            f"{url}\n\n"
            "The link works once. If it was not you, ignore this email — your "
            "password has not changed, and nobody can use this link without it."
        ),
    )


def email_verification_url(token: str) -> str:
    return f"{settings.frontend_origin}/verify-email?token={quote(token)}"


def build_email_verification(*, to: str, full_name: str, token: str) -> Email:
    return Email(
        to=to,
        to_name=full_name,
        subject="Confirm your email address",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            "Confirm this address so we can send you session reminders and "
            "joining links:\n\n"
            f"{email_verification_url(token)}\n\n"
            "You don't have to — your account works either way. Without it, "
            "reminders may not reach you."
        ),
    )


def build_password_changed(*, to: str, full_name: str) -> Email:
    return Email(
        to=to,
        to_name=full_name,
        subject="Your Shevaani password was changed",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            "Your password has just been changed, and every other browser signed "
            "into this account has been signed out.\n\n"
            "If this wasn't you, reset your password immediately and tell us at "
            "the contact address on the site."
        ),
    )


# ------------------------------------------------------------------ sessions
#
# None of these carry a join link. The link is a bearer credential and is served
# only from the gated join endpoint — mailing it would put a session key in an
# inbox, in a forwarded thread, and in whatever indexes that inbox.


def build_session_reminder(
    *,
    to: str,
    full_name: str,
    timezone: str | None,
    title: str,
    starts_at: datetime,
    hours_before: int,
) -> Email:
    lead = (
        "starts in about an hour"
        if hours_before <= 1
        else f"is coming up in about {hours_before} hours"
    )
    return Email(
        to=to,
        to_name=full_name,
        subject=f"Reminder: {title} — {'in an hour' if hours_before <= 1 else 'tomorrow'}",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"Your session *{title}* {lead}.\n\n"
            f"When: {_local(starts_at, timezone)}\n\n"
            "Open your dashboard a few minutes before it starts and the Join "
            "button will appear there:\n\n"
            f"{settings.frontend_origin}/dashboard\n\n"
            "Your instructor will let you in from the waiting room."
        ),
    )


def build_feedback_report(
    *,
    to: str,
    full_name: str,
    title: str,
    report_md: str,
) -> Email:
    """The learner's GD feedback, sent on the instructor's explicit click.

    The report rides in the body — markdown reads fine as plain text — because
    the moment of "your feedback is here" should not require a login to mean
    anything. The dashboard link is for keeping it, not for reading it.
    """
    return Email(
        to=to,
        to_name=full_name,
        subject=f"Your feedback from {title}",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"Here's your personal feedback from *{title}*:\n\n"
            f"{report_md}\n\n"
            "It also lives on your dashboard, alongside feedback from your "
            "other sessions:\n\n"
            f"{settings.frontend_origin}/dashboard/feedback"
        ),
    )


def build_session_auto_cancelled(
    *,
    to: str,
    full_name: str,
    timezone: str | None,
    title: str,
    starts_at: datetime,
    credits_refunded: int,
) -> Email:
    """Under ``min_seats`` at T-2h. The learner did nothing wrong, so the mail
    leads with the refund rather than with the apology."""
    refund = (
        f"Your {credits_refunded} credit(s) are already back on your account "
        "and can be spent on any other session."
        if credits_refunded
        else "Nothing was charged for it."
    )
    return Email(
        to=to,
        to_name=full_name,
        subject=f"Cancelled: {title}",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"*{title}* on {_local(starts_at, timezone)} has been cancelled — not "
            "enough people had booked for it to be a discussion.\n\n"
            f"{refund}\n\n"
            f"Browse what else is on: {settings.frontend_origin}/discussions"
        ),
    )


def build_session_cancelled_by_us(
    *,
    to: str,
    full_name: str,
    timezone: str | None,
    title: str,
    starts_at: datetime,
    reason: str,
    credits_refunded: int,
) -> Email:
    """A superuser cancelled the session. Says why, because somebody decided to."""
    refund = (
        f"Your {credits_refunded} credit(s) have been refunded."
        if credits_refunded
        else "Nothing was charged for it."
    )
    return Email(
        to=to,
        to_name=full_name,
        subject=f"Cancelled: {title}",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"We've had to cancel *{title}* on {_local(starts_at, timezone)}.\n\n"
            f"Reason: {reason}\n\n"
            f"{refund}\n\n"
            f"Book something else here: {settings.frontend_origin}/discussions"
        ),
    )


def build_booking_cancelled(
    *,
    to: str,
    full_name: str,
    timezone: str | None,
    title: str,
    starts_at: datetime,
    credits_refunded: int,
) -> Email:
    """The learner cancelled their own booking. A receipt, not an apology — and
    it states the refund outcome plainly, because that is the one thing they will
    want to check."""
    refund = (
        f"{credits_refunded} credit(s) have gone back to your account."
        if credits_refunded
        else (
            f"This was inside the {settings.cancellation_full_refund_hours}-hour "
            "cut-off, so the credit was not returned."
        )
    )
    return Email(
        to=to,
        to_name=full_name,
        subject=f"You cancelled: {title}",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"You've cancelled your place in *{title}* on "
            f"{_local(starts_at, timezone)}.\n\n"
            f"{refund}"
        ),
    )


def build_waitlist_promoted(
    *,
    to: str,
    full_name: str,
    timezone: str | None,
    title: str,
    starts_at: datetime,
    credits_spent: int,
) -> Email:
    """A seat opened and we took a credit for it. They need to know before the
    session runs, or the first they hear of it is a missing credit."""
    return Email(
        to=to,
        to_name=full_name,
        subject=f"A seat opened: you're in for {title}",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"You were on the waiting list for *{title}* and a seat has come "
            "free, so you're now booked in.\n\n"
            f"When: {_local(starts_at, timezone)}\n"
            f"Charged: {credits_spent} credit(s)\n\n"
            "If you can no longer make it, cancel from your dashboard and the "
            f"credit comes back (up to {settings.cancellation_full_refund_hours} "
            "hours before the start):\n\n"
            f"{settings.frontend_origin}/dashboard"
        ),
    )


# --------------------------------------------------------------- instructors


def build_google_connection_lost(*, to: str, full_name: str, google_email: str) -> Email:
    """Their Google grant stopped working and we have retired it.

    Says what it means for them rather than what happened technically — the
    consequence is that their sessions cannot get a room, and the fix is two
    clicks. The likely causes are listed because one of them (revoking access on
    a phone months ago) is the sort of thing people genuinely do not remember.
    """
    return Email(
        to=to,
        to_name=full_name,
        subject="Reconnect your Google account — sessions can't get a Meet link",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"Google has stopped accepting our connection to {google_email}, so "
            "any session you host can no longer be given a meeting link. Sessions "
            "already in your calendar are unaffected; new ones will fail until "
            "this is fixed.\n\n"
            "Reconnecting takes a moment:\n\n"
            f"{settings.frontend_origin}/instructor\n\n"
            "This usually happens because access was revoked in a Google account's "
            "security settings, or because the account's password changed. Neither "
            "is a problem — reconnecting resolves it."
        ),
    )


# ------------------------------------------------------------------ billing


def build_credit_receipt(
    *,
    to: str,
    full_name: str,
    credits: int,
    amount_minor: int,
    currency: str,
    provider: str,
    payment_id: str,
) -> Email:
    return Email(
        to=to,
        to_name=full_name,
        subject=f"Receipt: {credits} Shevaani credits",
        body=_sign_off(
            f"Hi {full_name},\n\n"
            f"Thanks — your payment went through and {credits} credit(s) are on "
            "your account.\n\n"
            f"Amount: {_money(amount_minor, currency)}\n"
            f"Paid via: {provider.title()}\n"
            f"Reference: {payment_id}\n\n"
            f"Spend them here: {settings.frontend_origin}/discussions"
        ),
    )

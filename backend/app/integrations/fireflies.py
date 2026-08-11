"""Thin async Fireflies.ai client.

Fireflies is the notetaker: its bot ("Fred") joins the Meet, records, and
transcribes with speaker diarization. We drive it through their GraphQL API
with one platform-owned account — instructors never connect anything.

Same reasoning as ``integrations/google_calendar.py``: the surface we need is
two GraphQL calls, so raw httpx keeps the event loop free and the dependency
tree small.

The bot is sent by URL via ``addToLiveMeeting`` when the session starts (the
mutation only works on an ongoing meeting, which is why a cron dispatches it
rather than the meeting-creation job). It joins the lobby like any other
uninvited guest, so the instructor admits it once — the event description
already tells them to expect lobby knocks.

Transcript arrival is announced by the ``meeting.transcribed`` webhook
(HMAC-SHA256 over the raw body, ``X-Hub-Signature: sha256=<hex>``), carrying
only a ``meeting_id`` — the transcript itself is fetched here.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.integrations.payments import InvalidSignature

GRAPHQL_ENDPOINT = "https://api.fireflies.ai/graphql"

_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class FirefliesAPIError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class Sentence:
    """One diarized utterance. Times are seconds from the start of the call."""

    speaker: str
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Transcript:
    id: str
    title: str | None
    meeting_link: str | None
    duration_minutes: float | None
    sentences: list[Sentence]


async def _graphql(query: str, variables: dict) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            GRAPHQL_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.fireflies_api_key}"},
            json={"query": query, "variables": variables},
        )
    if not response.is_success:
        # 4xx other than 429 means the request itself is wrong — retrying won't help.
        retryable = response.status_code == 429 or response.status_code >= 500
        raise FirefliesAPIError(
            f"Fireflies returned {response.status_code}: {response.text[:500]}",
            retryable=retryable,
        )
    payload = response.json()
    if payload.get("errors"):
        # GraphQL errors arrive with HTTP 200. `too_many_requests` is the one
        # worth retrying; everything else is a bad query or a gone resource.
        messages = "; ".join(str(e.get("message", e)) for e in payload["errors"])
        raise FirefliesAPIError(
            f"Fireflies GraphQL error: {messages[:500]}",
            retryable="too_many_requests" in messages,
        )
    return payload["data"]


async def add_to_live_meeting(*, meeting_link: str, title: str, duration_minutes: int) -> bool:
    """Send the bot into an ongoing meeting. Rate-limited to 3 calls per 20
    minutes on Fireflies' side — fine at our session volume, and the reason
    the dispatch cron never sends more than a handful at once."""
    data = await _graphql(
        """
        mutation AddToLiveMeeting($meetingLink: String!, $title: String, $duration: Int) {
          addToLiveMeeting(meeting_link: $meetingLink, title: $title, duration: $duration) {
            success
          }
        }
        """,
        {
            "meetingLink": meeting_link,
            "title": title[:256],
            # Their accepted range; a session longer than 2h gets a truncated
            # transcript rather than a failed dispatch.
            "duration": max(15, min(120, duration_minutes)),
        },
    )
    return bool((data.get("addToLiveMeeting") or {}).get("success"))


async def fetch_transcript(transcript_id: str) -> Transcript:
    data = await _graphql(
        """
        query Transcript($id: String!) {
          transcript(id: $id) {
            id
            title
            meeting_link
            duration
            sentences { speaker_name text start_time end_time }
          }
        }
        """,
        {"id": transcript_id},
    )
    raw = data.get("transcript")
    if raw is None:
        raise FirefliesAPIError(f"Transcript {transcript_id} not found.", retryable=False)

    sentences = [
        Sentence(
            speaker=(s.get("speaker_name") or "Unknown").strip(),
            text=(s.get("text") or "").strip(),
            start=float(s.get("start_time") or 0.0),
            end=float(s.get("end_time") or 0.0),
        )
        for s in (raw.get("sentences") or [])
        if (s.get("text") or "").strip()
    ]
    return Transcript(
        id=raw["id"],
        title=raw.get("title"),
        meeting_link=raw.get("meeting_link"),
        duration_minutes=float(raw["duration"]) if raw.get("duration") is not None else None,
        sentences=sentences,
    )


def verify_webhook(raw_body: bytes, signature_header: str | None) -> None:
    """Fireflies signs the raw body with the webhook signing secret and sends
    ``X-Hub-Signature: sha256=<hexdigest>``. Same raw-bytes rule as the payment
    webhooks: verify the exact bytes that were sent, never a re-serialisation."""
    if not settings.fireflies_webhook_secret:
        raise InvalidSignature("Fireflies webhooks are not configured.")
    if not signature_header or not signature_header.startswith("sha256="):
        raise InvalidSignature("Missing signature.")

    expected = hmac.new(
        settings.fireflies_webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header.removeprefix("sha256=")):
        raise InvalidSignature("Signature verification failed.")

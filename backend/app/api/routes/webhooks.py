"""Provider webhooks.

These are the only unauthenticated endpoints in the API that change money, so
everything about them is shaped around one question: is this really from the
provider?

The answer is the signature, checked against the **raw** body. That is why both
handlers take ``await request.body()`` and hand the bytes straight to the
verifier — reading the parsed JSON and re-serialising it changes whitespace and
key order, and the signature is over the exact bytes that were sent. FastAPI's
usual pattern of declaring a Pydantic body model is exactly wrong here.

Status codes matter more than usual, because they drive the provider's retry
behaviour:

* **400** — the signature did not verify. Not retryable, and not something we
  want repeated: an unverified body is either a misconfigured secret or a forgery,
  and both are answered by rejecting it and telling a human.
* **200** — verified. Including for events we ignore, events for orders we don't
  recognise, and duplicates. All three are "received and understood, stop
  resending".
* **500** — only if we genuinely fell over. That is the one case where a retry
  helps, and the provider will oblige.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from app.api.deps import DbSession
from app.integrations import fireflies, slack
from app.integrations import payments as payment_integrations
from app.integrations.payments import InvalidSignature
from app.services import billing
from app.workers import queue

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    raw = await request.body()
    try:
        envelope = payment_integrations.verify_stripe(raw, stripe_signature)
    except InvalidSignature as exc:
        await _report_rejection("stripe", exc.message)
        raise

    return {"status": await billing.handle_webhook(db, envelope)}


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: DbSession,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
) -> dict[str, str]:
    raw = await request.body()
    try:
        envelope = payment_integrations.verify_razorpay(raw, x_razorpay_signature)
    except InvalidSignature as exc:
        await _report_rejection("razorpay", exc.message)
        raise

    return {"status": await billing.handle_webhook(db, envelope)}


@router.post("/fireflies")
async def fireflies_webhook(
    request: Request,
    x_hub_signature: str | None = Header(default=None, alias="X-Hub-Signature"),
) -> dict[str, str]:
    """Fireflies announcing that a meeting's transcript is ready.

    Not money, but the same shape as the payment hooks: verify the raw bytes,
    then 200 for everything we understood — including events we ignore —
    because 200 is what stops the retries. The payload is thin (an event name
    and a transcript id); the transcript itself is fetched by the worker, so
    a forged id could only make us fetch a transcript we then fail to match.
    """
    raw = await request.body()
    try:
        fireflies.verify_webhook(raw, x_hub_signature)
    except InvalidSignature as exc:
        await _report_rejection("fireflies", exc.message)
        raise

    payload = await request.json()
    # v2 sends {"event": "meeting.transcribed", "meeting_id": ...}; v1 sent
    # {"eventType": "Transcription completed", "meetingId": ...}. Accept both.
    event = payload.get("event") or payload.get("eventType") or ""
    transcript_id = payload.get("meeting_id") or payload.get("meetingId")
    if not transcript_id or "transcri" not in event.lower():
        return {"status": "ignored"}

    await queue.enqueue("ingest_fireflies_transcript", str(transcript_id))
    return {"status": "queued"}


async def _report_rejection(provider: str, reason: str) -> None:
    """A rejected webhook is worth a human's attention either way.

    If the secret is wrong, payments are silently not being credited and nobody
    will notice until a learner asks where their credits went. If it is not
    wrong, someone is posting forged events at us. Both want telling; neither is
    visible in a 400 that only the sender sees.
    """
    await slack.dispatch(slack.webhook_signature_failed(provider=provider, reason=reason))

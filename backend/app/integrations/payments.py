"""Payment providers behind one protocol.

The protocol has to cover two genuinely different flows, and pretending
otherwise is where this kind of abstraction usually goes wrong:

* **Stripe** hands back a hosted URL and the browser leaves the site.
* **Razorpay** hands back an order id that a client-side modal consumes; the
  browser never navigates away.

:class:`CheckoutSession` therefore carries both a ``redirect_url`` and a
``client_payload``, and exactly one of them is populated. The frontend branches
on which.

What is *not* here: anything that grants credits. Credits are granted by the
webhook handler against ``credit_ledger``, never by a return from checkout — the
buyer's browser coming back to a success page is not evidence of payment.

**Why raw HTTP instead of the vendor SDKs.** Both SDKs are synchronous and would
block the event loop inside an async request handler. The surface we need is one
POST per provider, so this follows the same reasoning as
``integrations/google_calendar.py`` and calls the REST APIs directly. The one
exception is Stripe's ``Webhook.construct_event``, which is used as-is: it is
pure local crypto with no I/O, and it gets the replay-window check right, which
is the part of signature verification people reimplement wrongly.

**The signature rules that actually bite**, both learned the hard way and both
enforced by :func:`verify_stripe`/:func:`verify_razorpay` taking ``bytes``:

* Verify against the **raw** request body. Parsing to JSON and re-serialising
  changes key order and whitespace, and the signature is over the exact bytes.
* Razorpay's **webhook** secret is not its key secret. They are different values
  configured in different places, and using the key secret fails every check —
  which looks identical to "someone is forging events".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import stripe

from app.core.config import settings
from app.models.billing import CreditPack
from app.models.enums import PaymentProvider as ProviderName
from app.models.user import User
from app.services.errors import DomainError

logger = logging.getLogger(__name__)

STRIPE_CHECKOUT_SESSIONS = "https://api.stripe.com/v1/checkout/sessions"
RAZORPAY_ORDERS = "https://api.razorpay.com/v1/orders"


def _sessions_label(credits: int) -> str:
    """A pack's size in sessions — the unit every buying screen speaks in.

    Credits are the ledger's unit and belong in the ledger. The provider's own
    payment page is the last place a buyer should have to divide by two in their
    head, and it is the one screen we do not control the rest of, so what we hand
    it has to already be in the right unit.

    Rounds up, for the same reason ``sessionPriceLabel`` does in
    ``frontend/lib/pricing.ts``: a pack short of a whole session must not read as
    nothing. Every seeded pack is an even number of credits, so this only matters
    for one adjusted by hand.
    """
    sessions = max(1, math.ceil(credits / settings.session_price_credits))
    return f"{sessions} session" if sessions == 1 else f"{sessions} sessions"

_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class PaymentNotConfigured(DomainError):
    """No credentials for the provider this buyer would be sent to."""

    status_code = 503
    code = "payment_not_configured"


class PaymentProviderError(DomainError):
    """The provider was reached and refused, or could not be reached at all."""

    status_code = 502
    code = "payment_provider_error"


class InvalidSignature(DomainError):
    """A webhook did not verify. Never tell the caller which part failed."""

    status_code = 400
    code = "invalid_signature"


@dataclass(frozen=True)
class CheckoutSession:
    """What the browser needs to actually pay.

    ``provider_order_id`` is the provider's handle for this attempt and is what
    the webhook will arrive quoting, so it is stored on the payment row.
    """

    provider: ProviderName
    provider_order_id: str
    #: Stripe: a hosted checkout URL to navigate to.
    redirect_url: str | None = None
    #: Razorpay: what the client-side modal needs. Public values only — never a
    #: secret key, and never anything the buyer could tamper with to change the
    #: amount, since the amount is re-read from the order server-side.
    client_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayStatus:
    """What the provider says about one order, asked for rather than pushed.

    ``amount_minor``/``currency`` echo what was actually captured, so the caller
    can cross-check its own row instead of trusting ``paid`` on its own — the
    same defence :func:`app.services.billing.handle_webhook` applies to events.
    ``None`` means the provider did not say, not that it matched.
    """

    paid: bool
    expired: bool = False
    amount_minor: int | None = None
    currency: str | None = None
    provider_payment_id: str | None = None


class PaymentAdapter(Protocol):
    name: ProviderName

    def is_configured(self) -> bool:
        """Whether credentials exist for this provider in this environment."""

    async def create_checkout(
        self,
        *,
        payment_id: uuid.UUID,
        pack: CreditPack,
        amount_minor: int,
        currency: str,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """Open an order with the provider and describe how to pay it.

        The amount arrives already quoted rather than being read off ``pack``:
        the pack stores one USD price, and which currency this buyer is paying in
        is a decision made in :mod:`app.services.billing`, not one an adapter
        should be able to reach a different answer on.
        """

    async def fetch_status(self, provider_order_id: str) -> GatewayStatus:
        """Ask the provider what happened to this order.

        This is the authoritative answer in the return flow: the buyer's browser
        arriving at the success page proves only that they have a browser, so
        nothing they carry with them decides anything. We ask the provider
        ourselves, server to server, over an authenticated connection.
        """

    def verify_return_signature(self, provider_order_id: str, payload: dict[str, str]) -> bool:
        """Whether a client-side return payload really came from the provider.

        Only Razorpay's modal hands the browser anything to check. Providers
        that return by redirect have nothing signed to offer, so this is ``True``
        for them — :meth:`fetch_status` is what actually gates the grant either
        way, and refusing here would only reject honest buyers.
        """


class StripeAdapter:
    name = ProviderName.STRIPE

    def is_configured(self) -> bool:
        return bool(settings.stripe_secret_key)

    async def create_checkout(
        self,
        *,
        payment_id: uuid.UUID,
        pack: CreditPack,
        amount_minor: int,
        currency: str,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        if not self.is_configured():
            raise PaymentNotConfigured(
                "Card payments are not switched on yet. Nothing has been charged."
            )

        # Prices are inline rather than referencing a Stripe Price object. That
        # was already the right call with one price list; with five quoted from
        # a USD base it is the only one — a Price object per pack per currency
        # is fifteen dashboard entries to keep in step by hand.
        form = {
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            # The webhook finds our row from this without a lookup table.
            "client_reference_id": str(payment_id),
            "customer_email": user.email,
            "metadata[payment_id]": str(payment_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": str(amount_minor),
            "line_items[0][price_data][product_data][name]": pack.name,
            "line_items[0][price_data][product_data][description]": (
                f"{_sessions_label(pack.credits)} of live spoken English practice"
            ),
        }

        payload = await _post(
            STRIPE_CHECKOUT_SESSIONS,
            data=form,
            headers={
                "Authorization": f"Bearer {settings.stripe_secret_key}",
                # Our own payment id. A retried request — a timeout the caller
                # re-sent, a double-clicked button — returns the same session
                # instead of opening a second one the buyer could also pay.
                "Idempotency-Key": f"checkout-{payment_id}",
            },
            provider="Stripe",
        )

        return CheckoutSession(
            provider=self.name,
            provider_order_id=payload["id"],
            redirect_url=payload["url"],
        )

    async def fetch_status(self, provider_order_id: str) -> GatewayStatus:
        payload = await _get(
            f"{STRIPE_CHECKOUT_SESSIONS}/{provider_order_id}",
            headers={"Authorization": f"Bearer {settings.stripe_secret_key}"},
            provider="Stripe",
        )
        # `payment_status`, not `status`. A session goes `complete` the moment the
        # buyer finishes the form, which for delayed methods is well before the
        # money settles — reading the wrong field grants credits on a bank
        # transfer that has not arrived.
        paid = payload.get("payment_status") == "paid"
        payment_intent = payload.get("payment_intent")
        return GatewayStatus(
            paid=paid,
            expired=payload.get("status") == "expired",
            amount_minor=payload.get("amount_total") if paid else None,
            currency=(payload.get("currency") or "").upper() or None,
            # Expanded objects come back as a dict; unexpanded as a bare id.
            provider_payment_id=(
                payment_intent.get("id") if isinstance(payment_intent, dict) else payment_intent
            ),
        )

    def verify_return_signature(self, provider_order_id: str, payload: dict[str, str]) -> bool:
        # Stripe returns by redirect to a URL we built. There is nothing signed
        # in it to check, and nothing in it is trusted: `fetch_status` decides.
        return True


class RazorpayAdapter:
    name = ProviderName.RAZORPAY

    def is_configured(self) -> bool:
        return bool(settings.razorpay_key_id and settings.razorpay_key_secret)

    #: No currency allow-list. Razorpay is offered in every currency we quote
    #: and the buyer chooses it knowingly, so the account's own capability is
    #: the authority rather than a list here that would have to be kept in step
    #: with it.
    #:
    #: What that costs: an account without international payments enabled will
    #: reject a non-INR order. That comes back from `_post` as a 502 saying
    #: "Razorpay refused to open the payment. Nothing has been charged." —
    #: accurate, and raised before a card is involved, so the buyer can simply
    #: use the other button. If those refusals become common, put the
    #: allow-list back in `services.billing.PROVIDER_CURRENCIES` rather than
    #: here; that is the layer the checkout page reads to grey a button out.

    async def create_checkout(
        self,
        *,
        payment_id: uuid.UUID,
        pack: CreditPack,
        amount_minor: int,
        currency: str,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        if not self.is_configured():
            raise PaymentNotConfigured(
                "Card and UPI payments are not switched on yet. Nothing has been charged."
            )
        code = currency.upper()

        payload = await _post(
            RAZORPAY_ORDERS,
            json_body={
                "amount": amount_minor,
                "currency": code,
                # Max 40 characters at Razorpay; a bare UUID is 36.
                "receipt": str(payment_id),
                "notes": {"payment_id": str(payment_id), "credits": str(pack.credits)},
            },
            headers={"Authorization": _basic_auth(
                settings.razorpay_key_id, settings.razorpay_key_secret
            )},
            provider="Razorpay",
        )

        return CheckoutSession(
            provider=self.name,
            provider_order_id=payload["id"],
            # Everything here reaches the browser, so everything here is public.
            # The amount is echoed for display only — Razorpay charges what the
            # order says, not what the modal was handed.
            client_payload={
                "key_id": settings.razorpay_key_id,
                "order_id": payload["id"],
                "amount": amount_minor,
                "currency": code,
                "name": "Shevaani",
                "description": _sessions_label(pack.credits),
                "prefill": {"name": user.full_name, "email": user.email},
                "success_url": success_url,
                "cancel_url": cancel_url,
            },
        )

    async def fetch_status(self, provider_order_id: str) -> GatewayStatus:
        payload = await _get(
            f"{RAZORPAY_ORDERS}/{provider_order_id}",
            headers={"Authorization": _basic_auth(
                settings.razorpay_key_id, settings.razorpay_key_secret
            )},
            provider="Razorpay",
        )
        paid = payload.get("status") == "paid"
        return GatewayStatus(
            paid=paid,
            # An order sits at `created`/`attempted` indefinitely — Razorpay has
            # no expiry to report, so an abandoned checkout stays open rather
            # than being called failed on our own initiative.
            expired=False,
            # `amount_paid`, not `amount`: the second is what we asked for, the
            # first is what arrived, and cross-checking against the request we
            # made ourselves would check nothing.
            amount_minor=payload.get("amount_paid") if paid else None,
            currency=(payload.get("currency") or "").upper() or None,
        )

    def verify_return_signature(self, provider_order_id: str, payload: dict[str, str]) -> bool:
        """Checkout.js hands the browser an HMAC over ``order_id|payment_id``.

        Signed with the **key secret** — the opposite of the webhook rule at the
        top of this module, which uses the webhook secret. They are different
        values and swapping them fails every check, so the two paths deliberately
        read different settings rather than sharing one "the Razorpay secret".
        """
        payment_id = payload.get("razorpay_payment_id")
        signature = payload.get("razorpay_signature")
        if not payment_id or not signature or not settings.razorpay_key_secret:
            return False
        expected = hmac.new(
            settings.razorpay_key_secret.encode(),
            f"{provider_order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


# ------------------------------------------------------------ HTTP plumbing


async def _post(
    url: str,
    *,
    headers: dict[str, str],
    provider: str,
    data: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One POST, with the provider's own error text kept out of the response.

    A failure here happens *before* any money moves, so the buyer can be told
    plainly that nothing was charged. The provider's message goes to the log,
    not to them — it routinely quotes account ids and internal reasons.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, headers=headers, data=data, json=json_body)
    except httpx.HTTPError as exc:
        raise PaymentProviderError(
            f"Could not reach {provider}. Nothing has been charged — please try again."
        ) from exc

    if not response.is_success:
        logger.error("%s %s -> %s: %s", provider, url, response.status_code, response.text[:500])
        raise PaymentProviderError(
            f"{provider} refused to open the payment. Nothing has been charged."
        )

    return response.json()


async def _get(url: str, *, headers: dict[str, str], provider: str) -> dict[str, Any]:
    """One GET, for asking a provider what happened to an order.

    Unlike :func:`_post` this runs *after* the buyer may have paid, so a failure
    here is not "nothing was charged" — it is "we could not find out". It raises
    rather than reporting a negative, because returning "not paid" on an
    unreachable provider would let a timeout look like a refusal and strand
    somebody who has genuinely been charged.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise PaymentProviderError(
            f"Could not reach {provider} to confirm your payment. Please try again in a moment."
        ) from exc

    if not response.is_success:
        logger.error("%s GET %s -> %s: %s", provider, url, response.status_code, response.text[:500])
        raise PaymentProviderError(
            f"{provider} could not confirm this payment. Please try again in a moment."
        )

    return response.json()


def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


# ------------------------------------------------------- signature checking


@dataclass(frozen=True)
class WebhookEnvelope:
    """A verified event, reduced to what the handler needs.

    ``event_id`` is the provider's own id and is what the uniqueness constraint
    on ``webhook_events`` is built around, so it must be the id of the *event*,
    never of the payment — providers send several events about one payment and
    keying on the payment would swallow all but the first.
    """

    provider: ProviderName
    event_id: str
    event_type: str
    payload: dict[str, Any]


def verify_stripe(raw_body: bytes, signature_header: str | None) -> WebhookEnvelope:
    if not settings.stripe_webhook_secret:
        raise InvalidSignature("Stripe webhooks are not configured.")
    if not signature_header:
        raise InvalidSignature("Missing signature.")

    try:
        # Handles the timestamp tolerance as well as the HMAC, which is the half
        # people leave out — without it a captured webhook can be replayed
        # forever.
        event = stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=signature_header,
            secret=settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise InvalidSignature("Signature verification failed.") from exc

    return WebhookEnvelope(
        provider=ProviderName.STRIPE,
        event_id=event["id"],
        event_type=event["type"],
        payload=json.loads(raw_body.decode()),
    )


def verify_razorpay(raw_body: bytes, signature_header: str | None) -> WebhookEnvelope:
    """Razorpay signs the raw body with the **webhook** secret — not the key
    secret. Using the wrong one fails every event, which is indistinguishable
    from an attack unless you already know to look."""
    if not settings.razorpay_webhook_secret:
        raise InvalidSignature("Razorpay webhooks are not configured.")
    if not signature_header:
        raise InvalidSignature("Missing signature.")

    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise InvalidSignature("Signature verification failed.")

    try:
        payload = json.loads(raw_body.decode())
    except ValueError as exc:
        raise InvalidSignature("Body is not JSON.") from exc

    # Razorpay does not put an event id in the body, so the delivery id from the
    # header is the only per-event identifier available. Falling back to a hash
    # of the body keeps idempotency working rather than turning a missing header
    # into a double credit grant.
    event_id = payload.get("id") or hashlib.sha256(raw_body).hexdigest()
    return WebhookEnvelope(
        provider=ProviderName.RAZORPAY,
        event_id=str(event_id),
        event_type=str(payload.get("event", "unknown")),
        payload=payload,
    )


_ADAPTERS: dict[ProviderName, PaymentAdapter] = {
    ProviderName.STRIPE: StripeAdapter(),
    ProviderName.RAZORPAY: RazorpayAdapter(),
}


def adapter_for(provider: ProviderName) -> PaymentAdapter:
    return _ADAPTERS[provider]


def is_ready(provider: ProviderName) -> bool:
    """Whether a buyer sent to this provider could actually complete a purchase.

    Credentials only — the adapters are implemented. This still matters because
    a deployment with Stripe keys and no Razorpay keys is normal, and the
    checkout page has to know before it renders a button.
    """
    return _ADAPTERS[provider].is_configured()


def configured_providers() -> list[ProviderName]:
    return [name for name, adapter in _ADAPTERS.items() if adapter.is_configured()]

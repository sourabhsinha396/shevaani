"""Credit packs, checkout, and turning a payment into credits.

The one rule worth stating up front: **starting a checkout never grants
credits.** It writes a `payments` row with status ``created`` and stops. Credits
are appended to `credit_ledger` only once the *provider* says the money moved.

There are two routes to that answer and they meet in :func:`settle_paid`:

* :func:`verify_payment` — the primary one. The buyer returns from checkout, and
  we ask the provider ourselves what happened to the order. Their browser is the
  trigger; the provider's reply is the evidence. Nothing the browser carries is
  trusted, so a hand-built return URL grants nothing.
* :func:`handle_webhook` — the backstop, for the buyer who pays and then closes
  the tab. Same checks, same grant, arrived at from the other direction.

Either can win the race and the loser is a no-op, which is what the row lock in
:func:`settle_paid` is for.

Currency is picked by the buyer's browser, which detected it from their own
timezone, and quoted server-side from the pack's USD base price by
:mod:`app.services.pricing`. The request carries a three-letter code and never
an amount, so there is no amount to tamper with — a forged code can only buy at
a different price we already publish.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations import payments as payment_integrations
from app.integrations import slack
from app.integrations.payments import WebhookEnvelope
from app.models.billing import CreditPack, Payment, WebhookEvent
from app.models.enums import CreditReason, PaymentProvider, PaymentStatus
from app.models.user import User
from app.services import credits, notifications, pricing
from app.services.errors import DomainError, NotFound
from app.services.scheduling import utc_now

logger = logging.getLogger(__name__)


#: What each provider is *allowed* to be offered for. ``None`` means "anything
#: we quote", which both are now.
#:
#: Razorpay used to be pinned to INR here, because a plain domestic account
#: refuses other currencies at the orders API. That pin is gone deliberately:
#: both gateways are offered in every currency and the buyer picks. If an
#: account cannot take the currency, Razorpay says so when the order is opened —
#: which surfaces as a 502 with "nothing has been charged", *before* a card is
#: involved. A pre-charge refusal is a safe failure; the alternative was a
#: button a buyer could see the reason for but never press.
PROVIDER_CURRENCIES: dict[PaymentProvider, frozenset[str] | None] = {
    PaymentProvider.RAZORPAY: None,
    PaymentProvider.STRIPE: None,
}


def can_settle(provider: PaymentProvider, currency: str) -> bool:
    allowed = PROVIDER_CURRENCIES.get(provider)
    return allowed is None or currency.upper() in allowed


def currency_for(user: User, requested: str | None = None) -> str:
    """What to price this caller in.

    Ordered: what the browser asked for, then the country on the account, then
    USD. The browser goes first because it is the only party that knows where
    the visitor actually is — it reads their timezone. The stored country is a
    fallback for a client that sent nothing at all.
    """
    if requested and pricing.is_supported(requested):
        return requested.upper()
    return pricing.currency_for_country(user.billing_country) or pricing.USD


def provider_for(user: User, currency: str) -> PaymentProvider:
    """Which gateway to *lead* with. Both are offered either way.

    This is a recommendation, not a capability check — the two came apart when
    Razorpay stopped being pinned to rupees. ``can_settle`` now says yes to
    everything, so leaning on it here would let a stored ``preferred_provider``
    of Razorpay — set from an Indian signup country — take the lead on a euro
    order, which is the wrong default: Stripe is the one built for cross-border
    cards.

    So the rule is by currency first. Rupees lead with Razorpay, which settles
    domestically and is the only one of the two doing UPI; everything else leads
    with Stripe. A stored preference breaks ties within rupees, where it means
    something, and is ignored outside them, where it does not.
    """
    code = pricing.coerce(currency)

    if code == pricing.INR:
        preferred = user.preferred_provider
        if preferred is not None and payment_integrations.is_ready(preferred):
            return preferred
        if payment_integrations.is_ready(PaymentProvider.RAZORPAY):
            return PaymentProvider.RAZORPAY
        return PaymentProvider.STRIPE

    # Falls back to Razorpay only when Stripe has no keys at all — a
    # Razorpay-only deployment should still lead with something usable.
    if payment_integrations.is_ready(PaymentProvider.STRIPE):
        return PaymentProvider.STRIPE
    if payment_integrations.is_ready(PaymentProvider.RAZORPAY):
        return PaymentProvider.RAZORPAY
    return PaymentProvider.STRIPE


@dataclass(frozen=True)
class ProviderOption:
    provider: PaymentProvider
    available: bool
    unavailable_reason: str | None = None


#: Said to the buyer, so it explains rather than states a rule. Only reachable
#: for a gateway this deployment has no keys for — currency no longer disables
#: anything, since both providers are offered in all of them.
_NOT_CONFIGURED = "Not switched on for this site yet."


def provider_options(user: User, currency: str) -> list[ProviderOption]:
    """Every payment method for this currency, recommended first.

    Ordering is the whole point of returning a list rather than a set. The first
    entry is what the page should lead with, and deciding that here keeps the
    reasoning — rupees settle domestically through Razorpay, which is also the
    only one of the two that does UPI — in the same module as
    :func:`provider_for`, which has to agree with it.

    Both are offered in every currency now, so in practice the only thing that
    marks one unavailable is a deployment with no keys for it. It is still
    rendered rather than dropped: "not switched on yet" is information, and a
    silently missing payment method looks like one we do not support.
    """
    code = pricing.coerce(currency)
    recommended = provider_for(user, code)
    ordered = [recommended, *(p for p in PaymentProvider if p is not recommended)]

    options: list[ProviderOption] = []
    for provider in ordered:
        if not can_settle(provider, code):
            options.append(ProviderOption(provider, False, _NOT_CONFIGURED))
        elif not payment_integrations.is_ready(provider):
            options.append(ProviderOption(provider, False, _NOT_CONFIGURED))
        else:
            options.append(ProviderOption(provider, True))
    return options


async def list_packs(db: AsyncSession) -> Sequence[CreditPack]:
    """Every pack on sale. Not filtered by currency any more — a pack is one row
    with one USD price, and the caller quotes it into whatever they are showing."""
    result = await db.execute(
        select(CreditPack).where(CreditPack.is_active.is_(True)).order_by(CreditPack.credits)
    )
    return list(result.scalars().all())


class ProviderCannotSettle(DomainError):
    """The buyer picked a gateway that cannot take the currency they are in."""

    status_code = 400
    code = "provider_currency_mismatch"


async def start_checkout(
    db: AsyncSession,
    user: User,
    pack_id: uuid.UUID,
    currency: str | None = None,
    provider: PaymentProvider | None = None,
) -> tuple[Payment, payment_integrations.CheckoutSession]:
    """Open an order with the provider and record the attempt.

    The row is built complete and inserted once, rather than inserted and then
    patched with the provider's order id — ``provider_order_id`` is NOT NULL and
    a half-written payment is not a state worth being able to represent. The id
    is generated here so the adapter can hand it to the provider as the
    reference the webhook will quote back.

    If the provider succeeds and the insert then fails, the order is orphaned at
    the provider and no credits are granted. That is the safe direction, and
    reconciling those is ITC-52's problem, not something to solve by granting
    optimistically here.
    """
    pack = await db.get(CreditPack, pack_id)
    if pack is None or not pack.is_active:
        raise NotFound("That credit pack is no longer available.")

    # Quoted here, from the pack's stored USD cents, by the same function that
    # produced the price the buyer was shown. The request carried a currency
    # code and no amount, so there was never an amount to tamper with.
    code = currency_for(user, currency)
    amount_minor = pricing.quote_minor(pack.usd_cents, code)

    # An explicit choice is honoured, not treated as a hint — but it is checked
    # first. Silently substituting another gateway would charge somebody through
    # a company they did not pick, which is worse than refusing.
    if provider is None:
        provider = provider_for(user, code)
    elif not can_settle(provider, code):
        raise ProviderCannotSettle(
            f"{provider.value.title()} cannot take {code} payments. "
            "Nothing has been charged."
        )
    adapter = payment_integrations.adapter_for(provider)

    payment_id = uuid.uuid4()
    session = await adapter.create_checkout(
        payment_id=payment_id,
        pack=pack,
        amount_minor=amount_minor,
        currency=code,
        user=user,
        success_url=f"{settings.frontend_origin}/checkout/success?payment={payment_id}",
        cancel_url=f"{settings.frontend_origin}/checkout/cancelled?payment={payment_id}",
    )

    payment = Payment(
        id=payment_id,
        user_id=user.id,
        pack_id=pack.id,
        provider=provider,
        provider_order_id=session.provider_order_id,
        # The quote, not a reference to it: the price the buyer agreed to is a
        # fact about this purchase and must survive both the pack being
        # re-priced and the exchange rate being edited.
        amount_minor=amount_minor,
        currency=code,
        credits=pack.credits,
        status=PaymentStatus.CREATED,
    )
    db.add(payment)
    await db.flush()
    return payment, session


async def get_payment(db: AsyncSession, user: User, payment_id: uuid.UUID) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        # Same error for "no such payment" and "not yours" — the id is a UUID,
        # but there is no reason to confirm one exists to someone who cannot see it.
        raise NotFound("Payment not found.")
    return payment


async def _lock_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    """Re-read a payment with its row locked, for the stretch that grants.

    ``populate_existing`` is the load-bearing part. This row has usually been
    read already in the same session — :func:`verify_payment` reads it to check
    ownership before it ever reaches here — and SQLAlchemy's identity map hands
    back that same instance with its *old* attributes unless told otherwise. The
    lock would then be held over a status Python still believes is ``created``
    while the database says ``paid``, and the guard in :func:`settle_paid` would
    wave a second grant through. Refreshing is what makes the lock mean anything.
    """
    result = await db.execute(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


# ------------------------------------------------------------- settling up


@dataclass(frozen=True)
class Settlement:
    """What happened when a provider's "this is paid" was applied to a row."""

    outcome: str
    #: Set when the outcome was a refusal, for the caller to record.
    error: str | None = None


async def settle_paid(
    db: AsyncSession,
    payment: Payment,
    *,
    source: str,
    amount_minor: int | None = None,
    currency: str | None = None,
    provider_payment_id: str | None = None,
) -> Settlement:
    """Cross-check a provider's claim and, if it holds, grant the credits.

    **The only place a payment becomes PAID.** Two routes reach it — a webhook
    the provider pushed and a verify the buyer's return triggered — and they must
    not be able to disagree, nor to both grant. The caller is required to hold a
    row lock on ``payment``; the ``PAID`` check below is the idempotency guard,
    and without the lock two concurrent callers would both pass it.

    ``amount_minor``/``currency`` are what the provider says it captured. They
    are checked against our own row rather than trusted: a mismatch means the
    money that moved is not the money we quoted, and granting on it would be
    paying out on somebody else's arithmetic. ``None`` means the provider did not
    say, which is not the same as agreeing, so it skips the check rather than
    failing it.
    """
    if payment.status == PaymentStatus.PAID:
        # Normal, not suspicious: Razorpay sends `order.paid` and
        # `payment.captured` for one purchase, and the buyer may reload the
        # success page on top of either.
        return Settlement("already paid")

    if amount_minor is not None and amount_minor != payment.amount_minor:
        error = (
            f"Amount mismatch: provider says {amount_minor}, "
            f"payment says {payment.amount_minor}."
        )
        await slack.dispatch(
            slack.webhook_signature_failed(
                provider=payment.provider.value,
                reason=f"amount mismatch on order {payment.provider_order_id} ({source})",
            )
        )
        logger.error("Amount mismatch on payment %s via %s", payment.id, source)
        return Settlement("amount mismatch", error)

    # Same reasoning one currency along, and it matters more now that five are
    # in play: 2,900 of the wrong minor unit is a real amount that passes the
    # check above, and ₹29 is not $29.
    if currency is not None and currency != payment.currency:
        error = (
            f"Currency mismatch: provider says {currency}, "
            f"payment says {payment.currency}."
        )
        await slack.dispatch(
            slack.webhook_signature_failed(
                provider=payment.provider.value,
                reason=f"currency mismatch on order {payment.provider_order_id} ({source})",
            )
        )
        logger.error("Currency mismatch on payment %s via %s", payment.id, source)
        return Settlement("currency mismatch", error)

    payment.status = PaymentStatus.PAID
    payment.paid_at = utc_now()
    payment.provider_payment_id = provider_payment_id
    payment.failure_reason = None

    await credits.grant(
        db,
        payment.user_id,
        payment.credits,
        CreditReason.PURCHASE,
        payment_id=payment.id,
        note=f"{payment.credits} credits via {payment.provider.value}",
    )

    await notifications.credit_receipt(db, payment)
    await slack.dispatch(
        slack.payment_succeeded(
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            credits=payment.credits,
            provider=payment.provider.value,
        )
    )
    return Settlement("credited")


async def verify_payment(
    db: AsyncSession,
    user: User,
    payment_id: uuid.UUID,
    return_payload: dict[str, str] | None = None,
) -> Payment:
    """Ask the provider what happened, and apply the answer. The primary path.

    The buyer's browser landing back on our success page is not evidence of
    anything, so nothing it carries decides the outcome: we re-fetch the order
    server-side and the provider's answer is the only thing that can grant. The
    Razorpay return payload, when present, is checked too — but as an additional
    barrier, never as a substitute for asking.

    Safe to call repeatedly. A ``PAID`` payment returns untouched, so a buyer
    refreshing the success page — or bookmarking it and coming back next year —
    re-grants nothing.

    ``FAILED`` is deliberately *not* terminal here. Razorpay's ``payment.failed``
    fires per attempt while the order stays open, so a buyer whose first card was
    declined and whose second worked would otherwise be stranded by our own
    record of the first.
    """
    payment = await get_payment(db, user, payment_id)
    if payment.status in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
        return payment

    adapter = payment_integrations.adapter_for(payment.provider)
    if return_payload and not adapter.verify_return_signature(
        payment.provider_order_id, return_payload
    ):
        # Someone hand-built a return. Say nothing about which part failed.
        raise payment_integrations.InvalidSignature(
            "We couldn't verify that payment. Nothing has been added to your balance."
        )

    # Asked before the lock is taken: this is a round trip to the provider, and
    # holding a row lock across it would block the webhook for its duration.
    status = await adapter.fetch_status(payment.provider_order_id)

    locked = await _lock_payment(db, payment.id)
    if locked is None:  # pragma: no cover — the row was read a moment ago
        raise NotFound("Payment not found.")

    if status.paid:
        settlement = await settle_paid(
            db,
            locked,
            source="return",
            amount_minor=status.amount_minor,
            currency=status.currency,
            provider_payment_id=status.provider_payment_id,
        )
        if settlement.error is not None:
            # Money moved, but not the money we quoted. Park it for a human
            # rather than granting or telling the buyer it failed.
            locked.failure_reason = settlement.error
    elif status.expired and locked.status == PaymentStatus.CREATED:
        locked.status = PaymentStatus.FAILED
        locked.failure_reason = "The payment window closed before it was completed."

    await db.flush()
    return locked


async def list_payments(db: AsyncSession, user: User, limit: int = 50) -> Sequence[Payment]:
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ------------------------------------------------------------------ webhooks


@dataclass(frozen=True)
class _Outcome:
    """What a provider is telling us about one order."""

    order_id: str
    paid: bool
    provider_payment_id: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    reason: str | None = None


#: Events that move a payment. Anything else is recorded and ignored — providers
#: send a great deal of chatter, and a handler that tries to interpret all of it
#: is a handler that will one day interpret something wrongly.
_STRIPE_PAID = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
_STRIPE_FAILED = {"checkout.session.expired", "checkout.session.async_payment_failed"}
_RAZORPAY_PAID = {"order.paid", "payment.captured"}
_RAZORPAY_FAILED = {"payment.failed"}


def _read_stripe(envelope: WebhookEnvelope) -> _Outcome | None:
    obj: dict[str, Any] = envelope.payload.get("data", {}).get("object", {})
    order_id = obj.get("id")
    if not order_id:
        return None

    if envelope.event_type in _STRIPE_PAID:
        # `completed` fires for asynchronous methods before the money settles,
        # so the session's own payment_status is the thing to trust, not the
        # event name.
        if obj.get("payment_status") != "paid":
            return _Outcome(order_id=order_id, paid=False, reason="Awaiting payment.")
        return _Outcome(
            order_id=order_id,
            paid=True,
            provider_payment_id=obj.get("payment_intent"),
            amount_minor=obj.get("amount_total"),
            currency=(obj.get("currency") or "").upper() or None,
        )
    if envelope.event_type in _STRIPE_FAILED:
        return _Outcome(order_id=order_id, paid=False, reason=envelope.event_type)
    return None


def _read_razorpay(envelope: WebhookEnvelope) -> _Outcome | None:
    entities: dict[str, Any] = envelope.payload.get("payload", {})
    payment = entities.get("payment", {}).get("entity", {})
    order = entities.get("order", {}).get("entity", {})

    order_id = payment.get("order_id") or order.get("id")
    if not order_id:
        return None

    if envelope.event_type in _RAZORPAY_PAID:
        return _Outcome(
            order_id=order_id,
            paid=True,
            provider_payment_id=payment.get("id"),
            # On `order.paid` the payment entity is present too; on the rare
            # occasion it isn't, fall back to the order's own amount.
            amount_minor=payment.get("amount") or order.get("amount"),
            currency=(payment.get("currency") or order.get("currency") or "").upper() or None,
        )
    if envelope.event_type in _RAZORPAY_FAILED:
        return _Outcome(
            order_id=order_id,
            paid=False,
            reason=payment.get("error_description") or "Payment failed at the provider.",
        )
    return None


async def handle_webhook(db: AsyncSession, envelope: WebhookEnvelope) -> str:
    """Record a verified provider event and apply it. Insert first, then process.

    The backstop, not the main path — :func:`verify_payment` usually gets there
    first, because the buyer's browser is back before the provider's delivery
    is. What this still covers is the tab closed on the provider's page, which
    no amount of return-flow polling will ever see.

    The insert is the idempotency mechanism, not a log of one: ``webhook_events``
    is unique on ``(provider, event_id)``, so a replayed delivery — and providers
    replay aggressively whenever a response is slow — loses the race to its own
    first copy and does nothing. Doing it the other way round (process, then
    record) leaves a window in which a retry grants a second batch of credits.

    Returns a short string for the response body and the logs. It is never an
    error the provider should retry: an event we could not interpret is our
    problem, and telling a provider to keep resending it does not make it ours
    any faster.
    """
    now = utc_now()
    event = WebhookEvent(
        provider=envelope.provider,
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        payload=envelope.payload,
        received_at=now,
    )
    db.add(event)
    try:
        # Nested so that losing this race rolls back only the duplicate insert
        # and leaves the session usable.
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        return "duplicate"

    outcome = (
        _read_stripe(envelope)
        if envelope.provider == PaymentProvider.STRIPE
        else _read_razorpay(envelope)
    )
    if outcome is None:
        event.processed_at = now
        return "ignored"

    result = await db.execute(
        select(Payment)
        .where(
            Payment.provider == envelope.provider,
            Payment.provider_order_id == outcome.order_id,
        )
        # Locked so two events about the same order cannot both pass the
        # "already paid?" check below and grant twice.
        .with_for_update()
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        # Not necessarily an attack: a test event from the provider's dashboard,
        # or an order opened by a deployment pointed at the same account.
        event.processing_error = f"No payment for order {outcome.order_id}."
        event.processed_at = now
        logger.warning("Webhook for unknown order %s (%s)", outcome.order_id, envelope.provider)
        return "unknown order"

    if not outcome.paid:
        if payment.status == PaymentStatus.CREATED:
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = outcome.reason
        event.processed_at = now
        return "failed"

    settlement = await settle_paid(
        db,
        payment,
        source="webhook",
        amount_minor=outcome.amount_minor,
        currency=outcome.currency,
        provider_payment_id=outcome.provider_payment_id,
    )
    event.processing_error = settlement.error
    event.processed_at = now
    return settlement.outcome

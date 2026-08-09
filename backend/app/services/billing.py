"""Credit packs, checkout, and the webhook that turns a payment into credits.

The one rule worth stating up front: **starting a checkout never grants
credits.** It writes a `payments` row with status ``created`` and stops. Credits
are appended to `credit_ledger` by :func:`handle_webhook`, once the provider says
the money moved. A buyer returning to the success page proves only that they have
a browser.

Currency is picked from the learner's billing country and never converted. A ₹
price list and a $ price list are separate `credit_packs` rows, so "which pack"
and "which currency" resolve together or not at all.
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
from app.services import credits, notifications
from app.services.errors import DomainError, NotFound
from app.services.scheduling import utc_now

logger = logging.getLogger(__name__)

INR = "INR"
USD = "USD"


class PackUnavailable(DomainError):
    status_code = 409
    code = "pack_unavailable"


def currency_for(user: User) -> str:
    """India pays in rupees, everyone else in dollars.

    Keyed on the country captured at signup rather than on request geography, so
    a learner's price does not change because they opened the site on holiday.
    """
    return INR if (user.billing_country or "").upper() == "IN" else USD


def provider_for(user: User) -> PaymentProvider:
    if user.preferred_provider is not None:
        return user.preferred_provider
    return (
        PaymentProvider.RAZORPAY
        if (user.billing_country or "").upper() == "IN"
        else PaymentProvider.STRIPE
    )


async def list_packs(db: AsyncSession, currency: str) -> Sequence[CreditPack]:
    result = await db.execute(
        select(CreditPack)
        .where(CreditPack.is_active.is_(True), CreditPack.currency == currency.upper())
        .order_by(CreditPack.credits)
    )
    return list(result.scalars().all())


async def start_checkout(
    db: AsyncSession, user: User, pack_id: uuid.UUID
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

    expected = currency_for(user)
    if pack.currency != expected:
        # Guards against a buyer posting the id of the other currency's row and
        # paying ₹499 worth of dollars, or vice versa.
        raise PackUnavailable(
            f"That pack is priced in {pack.currency}; your account is billed in {expected}."
        )

    provider = provider_for(user)
    adapter = payment_integrations.adapter_for(provider)

    payment_id = uuid.uuid4()
    session = await adapter.create_checkout(
        payment_id=payment_id,
        pack=pack,
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
        # Copied off the pack, not referenced: the price the buyer agreed to is
        # a fact about this purchase and must survive the pack being re-priced.
        amount_minor=pack.amount_minor,
        currency=pack.currency,
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

    if payment.status == PaymentStatus.PAID:
        # A second event about a payment we already credited — normal, since
        # `order.paid` and `payment.captured` both arrive for the same purchase.
        event.processed_at = now
        return "already paid"

    # The amount is re-checked against our own row rather than trusted from the
    # event. A mismatch means the order was opened against a different price
    # than the one we recorded, and granting credits for it would be paying out
    # on someone else's arithmetic.
    if outcome.amount_minor is not None and outcome.amount_minor != payment.amount_minor:
        event.processing_error = (
            f"Amount mismatch: provider says {outcome.amount_minor}, "
            f"payment says {payment.amount_minor}."
        )
        event.processed_at = now
        await slack.dispatch(
            slack.webhook_signature_failed(
                provider=envelope.provider.value,
                reason=f"amount mismatch on order {outcome.order_id}",
            )
        )
        logger.error("Webhook amount mismatch on payment %s", payment.id)
        return "amount mismatch"

    payment.status = PaymentStatus.PAID
    payment.paid_at = now
    payment.provider_payment_id = outcome.provider_payment_id

    await credits.grant(
        db,
        payment.user_id,
        payment.credits,
        CreditReason.PURCHASE,
        payment_id=payment.id,
        note=f"{payment.credits} credits via {payment.provider.value}",
    )
    event.processed_at = now

    await notifications.credit_receipt(db, payment)
    await slack.dispatch(
        slack.payment_succeeded(
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            credits=payment.credits,
            provider=payment.provider.value,
        )
    )
    return "credited"

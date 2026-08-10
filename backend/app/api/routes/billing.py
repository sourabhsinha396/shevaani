"""Credit packs and checkout (ITC-51).

`/packs` is the one route here that does not require an account. It is a price
list — the same one the marketing pages show — and serving it publicly is what
lets `/pricing` and the homepage render real prices instead of a hand-copied
duplicate that drifts. Everything that touches a payment stays authenticated.

Prices no longer depend on the caller. A pack has one USD price and is quoted
into every supported currency on the way out, so an anonymous visitor and a
signed-in buyer see the same numbers, and which one gets charged is decided by
the currency their browser detected rather than by a country on the account.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.api.ratelimit import limiter
from app.core.ratelimit import CHECKOUT
from app.integrations import payments as payment_integrations
from app.models.billing import CreditPack
from app.schemas.billing import (
    BillingProfileOut,
    CheckoutIn,
    CheckoutOut,
    CreditPackOut,
    PaymentOut,
    ProviderOptionOut,
    VerifyIn,
)
from app.services import billing, pricing

router = APIRouter(prefix="/billing", tags=["billing"])

#: Three letters, and only ever read as a hint. Every path below runs it through
#: `pricing.coerce`, so an unknown code becomes USD rather than a 422.
CurrencyQuery = Annotated[str | None, Query(min_length=3, max_length=3)]


def _pack_out(pack: CreditPack, currency: str) -> CreditPackOut:
    prices = pricing.localized(pack.usd_cents)
    return CreditPackOut(
        id=pack.id,
        slug=pack.slug,
        name=pack.name,
        credits=pack.credits,
        usd_cents=pack.usd_cents,
        prices=prices,
        amount_minor=prices[currency],
        currency=currency,
    )


@router.get("/profile", response_model=BillingProfileOut)
async def billing_profile(user: CurrentUser, currency: CurrencyQuery = None) -> BillingProfileOut:
    """Which currency and gateway this caller would check out with.

    ``currency`` is what the browser detected. It is echoed back after being
    resolved, so a page that asked for something we do not sell learns that it
    is showing USD instead of assuming its own guess stuck.
    """
    code = billing.currency_for(user, currency)
    options = billing.provider_options(user, code)
    # First is the recommended one — `provider_options` orders it that way, and
    # `provider` is kept as its own field so a caller that only wants "who would
    # take this payment" does not have to know that.
    recommended = options[0].provider
    return BillingProfileOut(
        currency=code,
        provider=recommended,
        provider_ready=payment_integrations.is_ready(recommended),
        providers=[
            ProviderOptionOut(
                provider=option.provider,
                available=option.available,
                unavailable_reason=option.unavailable_reason,
            )
            for option in options
        ],
        supported_currencies=list(pricing.supported()),
    )


@router.get("/packs", response_model=list[CreditPackOut])
async def list_packs(
    db: DbSession,
    user: OptionalUser,
    currency: CurrencyQuery = None,
) -> list[CreditPackOut]:
    """The price list, quoted into every currency we sell in.

    ``currency`` only decides which entry is lifted into ``amount_minor`` for
    convenience; the full ``prices`` map is on every pack either way. Signing in
    changes nothing about the numbers — it is read here only to fall back to the
    country on the account when the caller sent no currency at all.
    """
    code = billing.currency_for(user, currency) if user else pricing.coerce(currency)
    return [_pack_out(pack, code) for pack in await billing.list_packs(db)]


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    dependencies=[Depends(limiter("checkout", CHECKOUT))],
)
async def start_checkout(payload: CheckoutIn, db: DbSession, user: CurrentUser) -> CheckoutOut:
    payment, session = await billing.start_checkout(
        db, user, payload.pack_id, payload.currency, payload.provider
    )
    return CheckoutOut(
        payment_id=payment.id,
        provider=payment.provider,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        credits=payment.credits,
        redirect_url=session.redirect_url,
        client_payload=session.client_payload,
    )


@router.get("/payments", response_model=list[PaymentOut])
async def my_payments(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[PaymentOut]:
    return [PaymentOut.model_validate(p) for p in await billing.list_payments(db, user, limit)]


@router.get("/payments/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: uuid.UUID, db: DbSession, user: CurrentUser) -> PaymentOut:
    """Reads the row without asking the provider anything.

    For anywhere that wants the recorded state — a receipt, a history row. The
    success page calls ``/verify`` instead, because "what do we have written
    down" and "what happened to the money" are different questions.
    """
    return PaymentOut.model_validate(await billing.get_payment(db, user, payment_id))


@router.post("/payments/{payment_id}/verify", response_model=PaymentOut)
async def verify_payment(
    payment_id: uuid.UUID, payload: VerifyIn, db: DbSession, user: CurrentUser
) -> PaymentOut:
    """Settle a payment against what the provider says, and grant if it paid.

    Called by the page the buyer lands on after checkout. Their arrival is only
    the trigger — the answer comes from a server-side fetch of the order, so
    calling this by hand with someone else's payment id gets a 404, and calling
    it with your own gets the truth rather than a grant.

    Idempotent: safe to call on every render and on a reload.
    """
    payment = await billing.verify_payment(
        db,
        user,
        payment_id,
        return_payload=payload.model_dump(exclude_none=True) or None,
    )
    return PaymentOut.model_validate(payment)

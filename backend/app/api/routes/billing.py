"""Credit packs and checkout (ITC-51).

Every route here is authenticated. Pack prices depend on the caller's billing
country, so there is no anonymous view of this data that would mean anything —
the marketing price list on `/pricing` is static copy and does not come from
here.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession
from app.api.ratelimit import limiter
from app.core.ratelimit import CHECKOUT
from app.integrations import payments as payment_integrations
from app.schemas.billing import (
    BillingProfileOut,
    CheckoutIn,
    CheckoutOut,
    CreditPackOut,
    PaymentOut,
)
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/profile", response_model=BillingProfileOut)
async def billing_profile(user: CurrentUser) -> BillingProfileOut:
    provider = billing.provider_for(user)
    return BillingProfileOut(
        currency=billing.currency_for(user),
        provider=provider,
        provider_ready=payment_integrations.is_ready(provider),
    )


@router.get("/packs", response_model=list[CreditPackOut])
async def list_packs(
    db: DbSession,
    user: CurrentUser,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> list[CreditPackOut]:
    """Packs the caller can actually buy.

    ``currency`` is an override for support and testing. It does not widen what
    can be purchased — ``start_checkout`` re-derives the currency from the
    account and refuses a pack that does not match.
    """
    packs = await billing.list_packs(db, currency or billing.currency_for(user))
    return [CreditPackOut.model_validate(p) for p in packs]


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    dependencies=[Depends(limiter("checkout", CHECKOUT))],
)
async def start_checkout(payload: CheckoutIn, db: DbSession, user: CurrentUser) -> CheckoutOut:
    payment, session = await billing.start_checkout(db, user, payload.pack_id)
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
    """Polled by the success page.

    It reports what the webhook has recorded, which is why it can legitimately
    still say ``created`` for a few seconds after a successful payment.
    """
    return PaymentOut.model_validate(await billing.get_payment(db, user, payment_id))

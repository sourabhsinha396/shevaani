from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import PaymentProvider, PaymentStatus
from app.schemas.common import ORMModel


class CreditPackOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    credits: int
    #: Paise or cents. The frontend formats it; the API never sends a float.
    amount_minor: int
    currency: str


class CheckoutIn(BaseModel):
    pack_id: uuid.UUID


class CheckoutOut(BaseModel):
    """How to pay. Exactly one of ``redirect_url`` / ``client_payload`` is set,
    depending on whether the provider hosts its own page."""

    payment_id: uuid.UUID
    provider: PaymentProvider
    amount_minor: int
    currency: str
    credits: int
    redirect_url: str | None = None
    client_payload: dict[str, object] = {}


class PaymentOut(ORMModel):
    id: uuid.UUID
    provider: PaymentProvider
    status: PaymentStatus
    amount_minor: int
    currency: str
    credits: int
    created_at: datetime
    paid_at: datetime | None = None
    failure_reason: str | None = None


class BillingProfileOut(BaseModel):
    """What the checkout page needs before it can render a price."""

    currency: str
    provider: PaymentProvider
    #: False when this deployment has no credentials for the provider the caller
    #: would be sent to — a normal state for, say, a Stripe-only environment.
    provider_ready: bool

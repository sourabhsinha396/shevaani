from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PaymentProvider, PaymentStatus
from app.schemas.common import ORMModel


class CreditPackOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    credits: int
    #: The base price, in US cents. Every entry in ``prices`` is quoted from it.
    usd_cents: int
    #: Minor units keyed by currency code — paise for INR, cents for the rest.
    #: Every supported currency is sent rather than only the one asked for, so a
    #: browser switching currency re-renders instead of re-fetching, and no
    #: client is ever in a position to run the conversion itself.
    prices: dict[str, int]
    #: The entry from ``prices`` for the currency this request asked for, so a
    #: caller that does not offer a switcher can ignore the map entirely.
    amount_minor: int
    currency: str


class CheckoutIn(BaseModel):
    pack_id: uuid.UUID
    #: What the buyer's browser detected. Advisory: the server re-derives it and
    #: re-quotes the price, and an unsupported code falls back to USD rather
    #: than failing a sale over a currency we simply do not list.
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    #: Which gateway the buyer picked. Unlike ``currency`` this is *not* purely
    #: advisory — it is honoured — so it is validated rather than coerced: a
    #: provider that cannot settle this currency, or that this deployment has no
    #: keys for, is refused instead of being quietly swapped for another. Absent
    #: means "whichever you recommend", which is the default the UI preselects.
    provider: PaymentProvider | None = None


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


class VerifyIn(BaseModel):
    """What Razorpay's modal hands the browser on success.

    Both fields absent is the normal Stripe case — it returns by redirect with
    nothing signed to pass on. They are checked when present and are never the
    thing that grants: the order is re-fetched from the provider either way, so
    an omitted or forged pair buys nothing.
    """

    razorpay_payment_id: str | None = Field(default=None, max_length=255)
    razorpay_signature: str | None = Field(default=None, max_length=255)


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


class ProviderOptionOut(BaseModel):
    """One payment method, and whether it can actually take this currency."""

    provider: PaymentProvider
    #: False means the button is shown but cannot be pressed. Kept visible on
    #: purpose: a buyer looking for UPI should find out that we have Razorpay
    #: and that it needs rupees, rather than concluding we do not offer it.
    available: bool
    #: Why not, in words a buyer can act on. ``None`` when ``available``.
    unavailable_reason: str | None = None


class BillingProfileOut(BaseModel):
    """What the checkout page needs before it can render a price."""

    #: The currency this caller would be charged in, for the currency they asked
    #: about. Echoed back rather than assumed, because an unsupported request
    #: silently becomes USD and the page should say so.
    currency: str
    provider: PaymentProvider
    #: False when this deployment has no credentials for the provider the caller
    #: would be sent to — a normal state for, say, a Stripe-only environment.
    provider_ready: bool
    #: Every method, **recommended first**. The order is the server's opinion,
    #: not the client's: which gateway suits a currency is a settlement question
    #: (rupees want Razorpay for UPI; everything else wants Stripe), and a page
    #: that decided it locally would have to be redeployed to change it.
    providers: list[ProviderOptionOut]
    #: Everything checkout will accept, for the currency switcher. Sent from the
    #: server so a deployment can drop a currency without a frontend release.
    supported_currencies: list[str]

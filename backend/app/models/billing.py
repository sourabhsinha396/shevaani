from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CreditReason, PaymentProvider, PaymentStatus
from app.models.types import pg_enum


class CreditPack(Base, UUIDPrimaryKey, Timestamped):
    """One row per pack, priced in USD.

    USD is the base list and the only price stored; INR, EUR, GBP and AUD are
    quoted from it at read time by :mod:`app.services.pricing`. A payment records
    its own ``amount_minor`` and ``currency``, so re-pricing a pack or moving an
    exchange rate never rewrites what somebody was charged.
    """

    __tablename__ = "credit_packs"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_credit_packs_slug"),
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint("usd_cents > 0", name="usd_cents_positive"),
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    #: US cents. Integer, always — never a float, and never a minor unit of some
    #: other currency: the whole conversion depends on knowing what this is.
    usd_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class Payment(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_order_id", name="uq_payments_provider_order"),
        CheckConstraint("amount_minor > 0", name="amount_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    pack_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("credit_packs.id", ondelete="SET NULL")
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        pg_enum(PaymentProvider, "payment_provider"), nullable=False
    )
    provider_order_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255))

    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), nullable=False, default=PaymentStatus.CREATED
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)


class CreditLedger(Base, UUIDPrimaryKey):
    """Append-only. Balance is SUM(delta) — there is deliberately no mutable
    balance column anywhere in this schema."""

    __tablename__ = "credit_ledger"
    __table_args__ = (CheckConstraint("delta <> 0", name="delta_non_zero"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[CreditReason] = mapped_column(pg_enum(CreditReason, "credit_reason"), nullable=False)

    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL")
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    payment: Mapped[Payment | None] = relationship()


class WebhookEvent(Base, UUIDPrimaryKey):
    """Insert-then-process. The unique constraint is what makes replays harmless."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        pg_enum(PaymentProvider, "payment_provider"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(Text)

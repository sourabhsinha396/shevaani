from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"
    SUPERUSER = "superuser"


class SessionKind(str, enum.Enum):
    GROUP = "group"
    ONE_ON_ONE = "one_on_one"


class SessionStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"  # seat held, awaiting payment
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    NO_SHOW = "no_show"


#: Statuses that occupy a seat. Everything else is either gone or never had one.
SEAT_HOLDING_STATUSES = (
    BookingStatus.PENDING,
    BookingStatus.CONFIRMED,
    BookingStatus.ATTENDED,
    BookingStatus.NO_SHOW,
)

#: Statuses that make a row participate in overlap constraints.
ACTIVE_BOOKING_STATUSES = SEAT_HOLDING_STATUSES


class MeetingStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class TranscriptStatus(str, enum.Enum):
    #: Sentences stored; speaker resolution has not finished cleanly.
    RECEIVED = "received"
    #: At least one speaker could not be matched confidently — an admin maps
    #: the leftovers in sqladmin, then feedback generation is re-run.
    NEEDS_REVIEW = "needs_review"
    #: Every speaker is mapped to a user or explicitly ignored.
    RESOLVED = "resolved"
    FAILED = "failed"


class FeedbackStatus(str, enum.Enum):
    #: Generated but not learner-visible. The instructor was in the room; the
    #: model was not — a human skim before publishing is the whole safety net.
    DRAFT = "draft"
    PUBLISHED = "published"


class BlockReason(str, enum.Enum):
    BUSY = "busy"
    HOLIDAY = "holiday"
    SICK = "sick"
    OTHER = "other"


class PaymentProvider(str, enum.Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class CreditReason(str, enum.Enum):
    PURCHASE = "purchase"
    BOOKING_SPEND = "booking_spend"
    BOOKING_REFUND = "booking_refund"
    SESSION_CANCELLED = "session_cancelled"
    ADMIN_GRANT = "admin_grant"
    ADMIN_REVOKE = "admin_revoke"
    #: The welcome credit, given once at registration. Its own reason rather
    #: than an ADMIN_GRANT with a note, so it can be counted and so the ledger
    #: does not tell a learner that Shevaani "granted" them something by hand.
    SIGNUP_BONUS = "signup_bonus"
    #: The referrer's free session, granted when somebody who joined through
    #: their link enrols. Written only by ``services.referrals``.
    REFERRAL_BONUS = "referral_bonus"

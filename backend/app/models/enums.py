from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"
    SUPERUSER = "superuser"


class CEFRLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

    @property
    def rank(self) -> int:
        return ["A1", "A2", "B1", "B2", "C1", "C2"].index(self.value)


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

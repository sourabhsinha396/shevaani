"""sqladmin views — the raw data plane.

Two rules shape everything here.

**Drill-down, not timestamp soup.** Every list leads somewhere: a session opens
onto its bookings and its meeting, an instructor onto their sessions and blocks,
a learner onto their ledger. Flat tables sorted by `created_at` are how you end
up unable to answer "what happened to this booking?" without SQL.

**Read-only where the schema says it must be.** `credit_ledger` is append-only —
balance is ``SUM(delta)``, so one hand-edited row silently corrupts a balance
forever. `payments` and `webhook_events` are reconciliation records; editing one
makes the books disagree with the provider. And `sessions.starts_at` can't be
touched here at all: `bookings` carries a denormalised `starts_at`/`ends_at` for
the learner-overlap exclusion constraint, and the two must move together in one
transaction. Rescheduling goes through
``services/session_admin.py::reschedule_session`` — i.e. the frontend admin.
"""

from __future__ import annotations

from sqladmin import ModelView

from app.models.availability import InstructorBlock
from app.models.billing import CreditLedger, CreditPack, Payment, WebhookEvent
from app.models.booking import Booking, JoinAccessLog
from app.models.contact import ContactMessage
from app.models.session import Session, SessionMeeting
from app.models.user import User


class ReadOnly:
    """Mixin for tables that must never be written from the data plane."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    category = "People"

    column_list = [User.full_name, User.email, User.role, User.level, User.is_active]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.full_name, User.email, User.role, User.created_at]
    column_default_sort = ("full_name", False)

    # Relationships in the detail view are what make this a graph rather than a
    # table: from a person you reach their Google grant, and from there the
    # sessions they host.
    column_details_exclude_list = [User.password_hash]

    # No create: a user without a properly hashed password is worse than no
    # user, and both privileged roles come from the CLI by design (decision 10).
    can_create = False
    # No delete: payments reference users with ON DELETE RESTRICT, so this would
    # fail confusingly. Deactivate instead.
    can_delete = False
    form_columns = [
        User.full_name,
        User.role,
        User.is_active,
        User.timezone,
        User.level,
        User.headline,
        User.bio,
        User.billing_country,
        User.preferred_provider,
    ]


class SessionAdmin(ModelView, model=Session):
    name = "Session"
    name_plural = "Sessions"
    icon = "fa-solid fa-calendar-days"
    category = "Scheduling"

    column_list = [
        Session.title,
        Session.kind,
        Session.status,
        Session.starts_at,
        Session.instructor,
        Session.max_seats,
        Session.price_credits,
    ]
    column_searchable_list = [Session.title, Session.topic]
    column_sortable_list = [Session.starts_at, Session.status, Session.title]
    column_default_sort = ("starts_at", True)
    column_details_list = [
        Session.id,
        Session.title,
        Session.topic,
        Session.description,
        Session.kind,
        Session.status,
        Session.starts_at,
        Session.ends_at,
        Session.level_min,
        Session.level_max,
        Session.min_seats,
        Session.max_seats,
        Session.price_credits,
        Session.prep_material_url,
        Session.cancelled_at,
        Session.cancellation_reason,
        Session.created_at,
        # The drill-down: from a session to who is in it and to its Meet.
        Session.instructor,
        Session.bookings,
        Session.meeting,
    ]

    can_create = False  # creation runs scheduling checks and enqueues the Meet job
    can_delete = False  # cancelling refunds credits; deleting the row would not

    # starts_at / ends_at / kind are absent on purpose — see the module docstring.
    form_columns = [
        Session.title,
        Session.topic,
        Session.description,
        Session.prep_material_url,
        Session.level_min,
        Session.level_max,
        Session.min_seats,
        Session.max_seats,
        Session.price_credits,
        Session.status,
    ]


class BookingAdmin(ReadOnly, ModelView, model=Booking):
    name = "Booking"
    name_plural = "Bookings"
    icon = "fa-solid fa-ticket"
    category = "Scheduling"

    # A booking's own timestamps mirror its session's and are covered by an
    # exclusion constraint, so this view reads; it never writes.
    column_list = [
        Booking.learner,
        Booking.session,
        Booking.status,
        Booking.starts_at,
        Booking.credits_spent,
        Booking.waitlist_position,
    ]
    column_sortable_list = [Booking.starts_at, Booking.status, Booking.created_at]
    column_default_sort = ("starts_at", True)
    column_details_list = [
        Booking.id,
        Booking.status,
        Booking.starts_at,
        Booking.ends_at,
        Booking.credits_spent,
        Booking.waitlist_position,
        Booking.hold_expires_at,
        Booking.first_joined_at,
        Booking.attendance_confirmed_at,
        Booking.cancelled_at,
        Booking.cancellation_reason,
        Booking.created_at,
        Booking.learner,
        Booking.session,
    ]


class SessionMeetingAdmin(ReadOnly, ModelView, model=SessionMeeting):
    name = "Meet link"
    name_plural = "Meet links"
    icon = "fa-solid fa-video"
    category = "Scheduling"

    # join_url is a bearer credential: anyone holding it can walk into the
    # lobby. It is not listed, not in the detail view, and not searchable.
    column_list = [
        SessionMeeting.session,
        SessionMeeting.status,
        SessionMeeting.host_google_email,
        SessionMeeting.attempts,
    ]
    column_details_list = [
        SessionMeeting.session_id,
        SessionMeeting.provider,
        SessionMeeting.status,
        SessionMeeting.host_google_email,
        SessionMeeting.calendar_event_id,
        SessionMeeting.attempts,
        SessionMeeting.last_error,
        SessionMeeting.created_at,
        SessionMeeting.updated_at,
        SessionMeeting.session,
    ]
    column_default_sort = ("updated_at", True)


class InstructorBlockAdmin(ModelView, model=InstructorBlock):
    name = "Blocked time"
    name_plural = "Blocked time"
    icon = "fa-solid fa-ban"
    category = "Scheduling"

    column_list = [
        InstructorBlock.instructor,
        InstructorBlock.starts_at,
        InstructorBlock.ends_at,
        InstructorBlock.reason,
        InstructorBlock.note,
    ]
    column_sortable_list = [InstructorBlock.starts_at, InstructorBlock.ends_at]
    column_default_sort = ("starts_at", True)

    # Creating or moving a block has to be refused when it covers a live session
    # (decision 11), and that check lives in the service layer. Removing one only
    # ever frees time up, so deleting is safe from here.
    can_create = False
    can_edit = False
    can_delete = True


class CreditLedgerAdmin(ReadOnly, ModelView, model=CreditLedger):
    name = "Ledger entry"
    name_plural = "Credit ledger"
    icon = "fa-solid fa-list-ol"
    category = "Money"

    column_list = [
        CreditLedger.created_at,
        CreditLedger.user_id,
        CreditLedger.delta,
        CreditLedger.reason,
        CreditLedger.note,
    ]
    column_sortable_list = [CreditLedger.created_at, CreditLedger.delta]
    column_default_sort = ("created_at", True)
    column_details_list = [
        CreditLedger.id,
        CreditLedger.user_id,
        CreditLedger.delta,
        CreditLedger.reason,
        CreditLedger.note,
        CreditLedger.booking_id,
        CreditLedger.payment,
        CreditLedger.created_at,
    ]


class PaymentAdmin(ReadOnly, ModelView, model=Payment):
    name = "Payment"
    name_plural = "Payments"
    icon = "fa-solid fa-credit-card"
    category = "Money"

    column_list = [
        Payment.created_at,
        Payment.user_id,
        Payment.provider,
        Payment.status,
        Payment.amount_minor,
        Payment.currency,
        Payment.credits,
    ]
    column_searchable_list = [Payment.provider_order_id, Payment.provider_payment_id]
    column_sortable_list = [Payment.created_at, Payment.status, Payment.amount_minor]
    column_default_sort = ("created_at", True)


class WebhookEventAdmin(ReadOnly, ModelView, model=WebhookEvent):
    name = "Webhook event"
    name_plural = "Webhook events"
    icon = "fa-solid fa-bolt"
    category = "Money"

    column_list = [
        WebhookEvent.received_at,
        WebhookEvent.provider,
        WebhookEvent.event_type,
        WebhookEvent.event_id,
        WebhookEvent.processed_at,
    ]
    column_searchable_list = [WebhookEvent.event_id, WebhookEvent.event_type]
    column_sortable_list = [WebhookEvent.received_at, WebhookEvent.processed_at]
    column_default_sort = ("received_at", True)


class CreditPackAdmin(ModelView, model=CreditPack):
    name = "Credit pack"
    name_plural = "Credit packs"
    icon = "fa-solid fa-coins"
    category = "Money"

    # The one genuinely editable money table: it is a price list, not a record
    # of something that happened. Prices are per currency and never converted.
    column_list = [
        CreditPack.name,
        CreditPack.slug,
        CreditPack.credits,
        CreditPack.amount_minor,
        CreditPack.currency,
        CreditPack.is_active,
    ]
    column_default_sort = ("credits", False)
    form_columns = [
        CreditPack.slug,
        CreditPack.name,
        CreditPack.credits,
        CreditPack.amount_minor,
        CreditPack.currency,
        CreditPack.is_active,
    ]


class JoinAccessLogAdmin(ReadOnly, ModelView, model=JoinAccessLog):
    name = "Join access"
    name_plural = "Join access log"
    icon = "fa-solid fa-door-open"
    category = "Audit"

    column_list = [
        JoinAccessLog.accessed_at,
        JoinAccessLog.session_id,
        JoinAccessLog.user_id,
        JoinAccessLog.granted,
        JoinAccessLog.denial_reason,
    ]
    column_sortable_list = [JoinAccessLog.accessed_at]
    column_default_sort = ("accessed_at", True)


class ContactMessageAdmin(ModelView, model=ContactMessage):
    name = "Contact message"
    name_plural = "Contact messages"
    icon = "fa-solid fa-envelope"
    category = "Audit"

    column_list = [
        ContactMessage.created_at,
        ContactMessage.name,
        ContactMessage.email,
        ContactMessage.subject,
        ContactMessage.handled_at,
    ]
    column_searchable_list = [ContactMessage.email, ContactMessage.subject]
    column_sortable_list = [ContactMessage.created_at, ContactMessage.handled_at]
    column_default_sort = ("created_at", True)

    can_create = False
    # What someone sent us is a record; only our handling of it is editable.
    form_columns = [ContactMessage.handled_at, ContactMessage.handled_note]


VIEWS = [
    UserAdmin,
    SessionAdmin,
    BookingAdmin,
    SessionMeetingAdmin,
    InstructorBlockAdmin,
    CreditLedgerAdmin,
    PaymentAdmin,
    WebhookEventAdmin,
    CreditPackAdmin,
    JoinAccessLogAdmin,
    ContactMessageAdmin,
]

"""sqladmin views — the raw data plane.

**Drill-down, not timestamp soup.** Every list leads somewhere: a session opens
onto its bookings and its meeting, an instructor onto their sessions and blocks,
a learner onto their ledger. Flat tables sorted by `created_at` are how you end
up unable to answer "what happened to this booking?" without SQL.

**Full CRUD on every table.** Nothing here is locked down: create, edit and
delete are open on all models and every column is editable. That is deliberate —
this is the operator's escape hatch, and the invariants it can break are yours to
keep. Worth knowing which ones they are:

- `credit_ledger` is append-only; balance is ``SUM(delta)``, so editing or
  deleting a row moves a balance with no record of why.
- `payments` and `webhook_events` are reconciliation records — editing one makes
  the books disagree with the provider.
- `sessions.starts_at`/`ends_at` are denormalised onto `bookings` for the
  learner-overlap exclusion constraint; the two must move together or the
  constraint no longer means anything. ``services/session_admin.py::
  reschedule_session`` does both in one transaction.
- Deleting a `user` that payments reference will be refused by
  ``ON DELETE RESTRICT`` at the database, not here.
"""

from __future__ import annotations

from sqladmin import ModelView

from app.models.availability import InstructorBlock
from app.models.billing import CreditLedger, CreditPack, Payment, WebhookEvent
from app.models.booking import Booking, JoinAccessLog
from app.models.contact import ContactMessage
from app.models.feedback import (
    MeetAlias,
    SessionFeedback,
    SessionTranscript,
    TranscriptSpeaker,
)
from app.models.impromptu import ImpromptuTopic
from app.models.referral import Referral
from app.models.session import (
    InstructorEngagement,
    OneOnOneSession,
    Session,
    SessionMeeting,
)
from app.models.settings import SiteSettings
from app.models.user import User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    category = "People"

    column_list = [User.full_name, User.email, User.role, User.is_active]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.full_name, User.email, User.role, User.created_at]
    column_default_sort = ("full_name", False)


class ReferralAdmin(ModelView, model=Referral):
    """Who brought whom. ``credited_at`` NULL means joined but not yet enrolled;
    set means the reward in ``reward_credits`` has been granted to the referrer.

    Editing ``credited_at`` by hand does not move any credits — the grant lives
    on the ledger. Blanking it *would* make the next settled payment of that
    referred user pay the referrer again, so treat it as append-only in spirit.
    """

    name = "Referral"
    name_plural = "Referrals"
    icon = "fa-solid fa-user-plus"
    category = "People"

    column_list = [
        Referral.referrer,
        Referral.referred_user,
        Referral.code_used,
        Referral.created_at,
        Referral.credited_at,
        Referral.reward_credits,
    ]
    column_sortable_list = [Referral.created_at, Referral.credited_at]
    column_default_sort = ("created_at", True)
    column_details_list = [
        Referral.id,
        Referral.referrer,
        Referral.referred_user,
        Referral.code_used,
        Referral.created_at,
        Referral.credited_at,
        Referral.reward_credits,
    ]


class SessionAdmin(ModelView, model=Session):
    name = "Group discussion"
    name_plural = "Group discussions"
    icon = "fa-solid fa-calendar-days"
    category = "Scheduling"

    column_list = [
        Session.title,
        Session.status,
        Session.starts_at,
        Session.instructor,
        Session.max_seats,
        Session.price_credits,
    ]
    column_searchable_list = [Session.title, Session.topic, Session.slug]
    column_sortable_list = [Session.starts_at, Session.status, Session.title]
    column_default_sort = ("starts_at", True)
    column_details_list = [
        Session.id,
        Session.title,
        Session.slug,
        Session.topic,
        Session.description,
        Session.status,
        Session.starts_at,
        Session.ends_at,
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


class OneOnOneSessionAdmin(ModelView, model=OneOnOneSession):
    """Its own list since 0009, which is most of the point of the split — the
    Sessions list is a curated catalogue again instead of it plus one row per
    booked hour."""

    name = "1:1 session"
    name_plural = "1:1 sessions"
    icon = "fa-solid fa-user-clock"
    category = "Scheduling"

    column_list = [
        OneOnOneSession.title,
        OneOnOneSession.status,
        OneOnOneSession.starts_at,
        OneOnOneSession.instructor,
        OneOnOneSession.price_credits,
    ]
    column_searchable_list = [OneOnOneSession.title]
    column_sortable_list = [OneOnOneSession.starts_at, OneOnOneSession.status]
    column_default_sort = ("starts_at", True)
    column_details_list = [
        OneOnOneSession.id,
        OneOnOneSession.title,
        OneOnOneSession.status,
        OneOnOneSession.starts_at,
        OneOnOneSession.ends_at,
        OneOnOneSession.price_credits,
        OneOnOneSession.cancelled_at,
        OneOnOneSession.cancellation_reason,
        OneOnOneSession.created_at,
        OneOnOneSession.instructor,
        # The learner is on the booking, not here — see the model docstring.
        OneOnOneSession.bookings,
        OneOnOneSession.meeting,
    ]


class InstructorEngagementAdmin(ModelView, model=InstructorEngagement):
    """The instructor calendar both session tables mirror into.

    Read it to answer "why was this hour refused?". **Editing a row here fixes
    nothing** — the triggers rewrite it from the session it mirrors on the next
    write, and an edit that disagrees with the source just makes the exclusion
    constraint refuse bookings that should have been fine.
    """

    name = "Instructor engagement"
    name_plural = "Instructor calendar"
    icon = "fa-solid fa-calendar-check"
    category = "Scheduling"

    column_list = [
        InstructorEngagement.starts_at,
        InstructorEngagement.ends_at,
        InstructorEngagement.source,
        InstructorEngagement.source_id,
        InstructorEngagement.instructor_id,
    ]
    column_sortable_list = [InstructorEngagement.starts_at, InstructorEngagement.source]
    column_default_sort = ("starts_at", True)


class BookingAdmin(ModelView, model=Booking):
    name = "Booking"
    name_plural = "Bookings"
    icon = "fa-solid fa-ticket"
    category = "Scheduling"

    column_list = [
        Booking.learner,
        Booking.session,
        Booking.one_on_one,
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
        # Exactly one of these is set — see `ck_bookings_exactly_one_parent`.
        Booking.session,
        Booking.one_on_one,
    ]


class SessionMeetingAdmin(ModelView, model=SessionMeeting):
    name = "Meet link"
    name_plural = "Meet links"
    icon = "fa-solid fa-video"
    category = "Scheduling"

    column_list = [
        SessionMeeting.session,
        SessionMeeting.one_on_one,
        SessionMeeting.status,
        SessionMeeting.host_google_email,
        SessionMeeting.attempts,
    ]
    column_details_list = [
        SessionMeeting.session_id,
        SessionMeeting.one_on_one_id,
        SessionMeeting.provider,
        SessionMeeting.status,
        SessionMeeting.join_url,
        SessionMeeting.host_google_email,
        SessionMeeting.calendar_event_id,
        SessionMeeting.attempts,
        SessionMeeting.last_error,
        SessionMeeting.created_at,
        SessionMeeting.updated_at,
        SessionMeeting.session,
        SessionMeeting.one_on_one,
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


class CreditLedgerAdmin(ModelView, model=CreditLedger):
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


class PaymentAdmin(ModelView, model=Payment):
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


class WebhookEventAdmin(ModelView, model=WebhookEvent):
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

    # A price list, not a record of something that happened. Editing `usd_cents`
    # re-prices every currency at once — the others are quoted from it, so there
    # is no ₹ field to forget.
    column_list = [
        CreditPack.name,
        CreditPack.slug,
        CreditPack.credits,
        CreditPack.usd_cents,
        CreditPack.is_active,
    ]
    column_default_sort = ("credits", False)


class JoinAccessLogAdmin(ModelView, model=JoinAccessLog):
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


class ImpromptuTopicAdmin(ModelView, model=ImpromptuTopic):
    """The free tool's topic bank. This is where new verticals get added —
    a ``track`` is just a string, so "Bank PO" exists the moment its first
    topic row does. Both ``category`` and ``track`` are shown to visitors
    verbatim; type them as you want them read."""

    name = "Impromptu topic"
    name_plural = "Impromptu topics"
    icon = "fa-solid fa-microphone-lines"
    category = "Platform"

    column_list = [
        ImpromptuTopic.text,
        ImpromptuTopic.category,
        ImpromptuTopic.track,
        ImpromptuTopic.difficulty,
        ImpromptuTopic.sort_order,
        ImpromptuTopic.is_active,
    ]
    column_searchable_list = [ImpromptuTopic.text, ImpromptuTopic.category, ImpromptuTopic.track]
    column_sortable_list = [ImpromptuTopic.sort_order, ImpromptuTopic.track, ImpromptuTopic.category]
    column_default_sort = ("sort_order", False)


class SiteSettingsAdmin(ModelView, model=SiteSettings):
    """The feature flags, as one row.

    The place to change these is the frontend admin at ``/admin/settings``,
    which is a labelled switch per flag and says what each one does. This view
    is the raw row, for when you want to see the timestamps or fix something the
    form cannot express.

    Two things this view will happily let you do, per the full-CRUD rule above:
    delete the row, which the application reads as "every flag at its default",
    i.e. everything on — recoverable by saving anything in ``/admin/settings``;
    and create a second one, which the ``id = 1`` check refuses at the database.

    ``__all__`` rather than a column list, so a flag added later shows up here
    without anyone remembering to come back and add it.
    """

    name = "Site setting"
    name_plural = "Site settings"
    icon = "fa-solid fa-toggle-on"
    category = "Platform"

    column_list = "__all__"


class SessionTranscriptAdmin(ModelView, model=SessionTranscript):
    """The GD pipeline's inbox. NEEDS_REVIEW means somebody in the room didn't
    match a roster name — fix the mapping under *Transcript speakers*; the
    half-hourly sweep notices and generates the reports."""

    name = "Transcript"
    name_plural = "Transcripts"
    icon = "fa-solid fa-file-lines"
    category = "Feedback"

    column_list = [
        SessionTranscript.session,
        SessionTranscript.status,
        SessionTranscript.duration_minutes,
        SessionTranscript.created_at,
    ]
    column_sortable_list = [SessionTranscript.created_at, SessionTranscript.status]
    column_default_sort = ("created_at", True)
    column_details_exclude_list = [SessionTranscript.sentences]


class TranscriptSpeakerAdmin(ModelView, model=TranscriptSpeaker):
    """The human half of identity resolution. A row with no user and no
    ``ignored`` tick is the question being asked: who is this? Set the user
    (or tick ignored for the bot / a stray guest) — nothing else to click."""

    name = "Transcript speaker"
    name_plural = "Transcript speakers"
    icon = "fa-solid fa-user-tag"
    category = "Feedback"

    column_list = [
        TranscriptSpeaker.speaker_label,
        TranscriptSpeaker.user,
        TranscriptSpeaker.ignored,
        TranscriptSpeaker.confidence,
        TranscriptSpeaker.resolved_via,
        TranscriptSpeaker.transcript,
    ]
    column_searchable_list = [TranscriptSpeaker.speaker_label]
    column_sortable_list = [TranscriptSpeaker.created_at, TranscriptSpeaker.confidence]
    column_default_sort = ("created_at", True)


class MeetAliasAdmin(ModelView, model=MeetAlias):
    """What the resolver has learned. Delete a row if a mapping was wrong —
    a bad alias silently mis-attributes every future transcript."""

    name = "Meet alias"
    name_plural = "Meet aliases"
    icon = "fa-solid fa-masks-theater"
    category = "Feedback"

    column_list = [MeetAlias.display_name, MeetAlias.user, MeetAlias.last_seen_at]
    column_searchable_list = [MeetAlias.display_name]
    column_sortable_list = [MeetAlias.last_seen_at]
    column_default_sort = ("last_seen_at", True)


class SessionFeedbackAdmin(ModelView, model=SessionFeedback):
    """Draft reports waiting for a human. Edit ``report_md`` freely; flipping
    ``status`` to published is what makes it learner-visible — set
    ``published_at`` too, the check constraint insists they travel together."""

    name = "Session feedback"
    name_plural = "Session feedback"
    icon = "fa-solid fa-comment-dots"
    category = "Feedback"

    column_list = [
        SessionFeedback.booking,
        SessionFeedback.status,
        SessionFeedback.generated_by,
        SessionFeedback.created_at,
        SessionFeedback.published_at,
    ]
    column_sortable_list = [SessionFeedback.created_at, SessionFeedback.status]
    column_default_sort = ("created_at", True)


VIEWS = [
    SiteSettingsAdmin,
    UserAdmin,
    ReferralAdmin,
    SessionAdmin,
    OneOnOneSessionAdmin,
    BookingAdmin,
    SessionMeetingAdmin,
    InstructorEngagementAdmin,
    InstructorBlockAdmin,
    CreditLedgerAdmin,
    PaymentAdmin,
    WebhookEventAdmin,
    CreditPackAdmin,
    JoinAccessLogAdmin,
    ContactMessageAdmin,
    ImpromptuTopicAdmin,
    SessionTranscriptAdmin,
    TranscriptSpeakerAdmin,
    MeetAliasAdmin,
    SessionFeedbackAdmin,
]

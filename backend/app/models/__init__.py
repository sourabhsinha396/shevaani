"""Import every model here so Alembic's autogenerate sees the full metadata."""

from app.models.auth import EmailVerificationToken, PasswordResetToken
from app.models.availability import InstructorBlock
from app.models.base import Base
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
from app.models.notifications import SessionReminder
from app.models.referral import Referral
from app.models.session import Session, SessionMeeting
from app.models.settings import SiteSettings
from app.models.user import GoogleCredential, User

__all__ = [
    "Base",
    "Booking",
    "ContactMessage",
    "CreditLedger",
    "CreditPack",
    "EmailVerificationToken",
    "InstructorBlock",
    "GoogleCredential",
    "ImpromptuTopic",
    "JoinAccessLog",
    "MeetAlias",
    "PasswordResetToken",
    "Payment",
    "Referral",
    "Session",
    "SessionFeedback",
    "SessionMeeting",
    "SessionReminder",
    "SessionTranscript",
    "TranscriptSpeaker",
    "SiteSettings",
    "User",
    "WebhookEvent",
]

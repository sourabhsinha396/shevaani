"""Import every model here so Alembic's autogenerate sees the full metadata."""

from app.models.auth import EmailVerificationToken, PasswordResetToken
from app.models.availability import InstructorBlock
from app.models.base import Base
from app.models.billing import CreditLedger, CreditPack, Payment, WebhookEvent
from app.models.booking import Booking, JoinAccessLog
from app.models.contact import ContactMessage
from app.models.notifications import SessionReminder
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
    "JoinAccessLog",
    "PasswordResetToken",
    "Payment",
    "Session",
    "SessionMeeting",
    "SessionReminder",
    "SiteSettings",
    "User",
    "WebhookEvent",
]

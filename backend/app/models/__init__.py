"""Import every model here so Alembic's autogenerate sees the full metadata."""

from app.models.availability import InstructorBlock
from app.models.base import Base
from app.models.billing import CreditLedger, CreditPack, Payment, WebhookEvent
from app.models.booking import Booking, JoinAccessLog
from app.models.session import Session, SessionMeeting
from app.models.user import GoogleCredential, User

__all__ = [
    "Base",
    "Booking",
    "CreditLedger",
    "CreditPack",
    "InstructorBlock",
    "GoogleCredential",
    "JoinAccessLog",
    "Payment",
    "Session",
    "SessionMeeting",
    "User",
    "WebhookEvent",
]

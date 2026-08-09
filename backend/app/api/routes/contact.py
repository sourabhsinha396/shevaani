"""Public contact form.

Payment providers require a working contact route before they approve a live
account, so this has to exist and has to be reachable without an account. That
makes it the only unauthenticated write endpoint on the API, hence the throttle.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.api.deps import DbSession, OptionalUser
from app.api.ratelimit import limiter
from app.core.ratelimit import CONTACT
from app.models.contact import ContactMessage
from app.schemas.common import Message
from app.schemas.contact import ContactIn
from app.services.errors import Conflict
from app.services.scheduling import utc_now

router = APIRouter(prefix="/contact", tags=["contact"])

#: Enough for a real conversation, low enough that the form is not a mail relay.
MAX_PER_HOUR = 5


@router.post(
    "",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
    # The per-address check below is the honest-user throttle; a script simply
    # varies the address. This one is keyed on where the request came from.
    dependencies=[Depends(limiter("contact", CONTACT))],
)
async def submit(payload: ContactIn, db: DbSession, user: OptionalUser) -> Message:
    email = payload.email.lower()
    since = utc_now() - timedelta(hours=1)

    recent = await db.execute(
        select(func.count(ContactMessage.id)).where(
            ContactMessage.email == email, ContactMessage.created_at >= since
        )
    )
    if int(recent.scalar_one()) >= MAX_PER_HOUR:
        raise Conflict(
            "That's a lot of messages in an hour — give us a chance to reply first.",
            code="rate_limited",
        )

    db.add(
        ContactMessage(
            name=payload.name.strip(),
            email=email,
            subject=payload.subject.strip(),
            body=payload.body.strip(),
            user_id=user.id if user else None,
            created_at=utc_now(),
        )
    )
    return Message(detail="Thanks — we'll reply to that address within two working days.")

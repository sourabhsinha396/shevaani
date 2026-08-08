from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, Instructor
from app.core.config import settings
from app.core.security import encrypt_secret
from app.integrations import google_calendar
from app.integrations.google_calendar import GoogleAPIError
from app.models.availability import InstructorBlock
from app.models.enums import UserRole
from app.models.user import GoogleCredential, User
from app.schemas.common import InstructorOut, Message, SlotOut
from app.schemas.session import BlockIn, BlockOut
from app.services import scheduling, session_admin
from app.services.errors import NotFound, PermissionDenied
from app.services.scheduling import utc_now

router = APIRouter(prefix="/instructors", tags=["instructors"])


@router.get("", response_model=list[InstructorOut])
async def list_instructors(db: DbSession) -> list[InstructorOut]:
    result = await db.execute(
        select(User)
        .where(
            User.role.in_([UserRole.INSTRUCTOR, UserRole.SUPERUSER]),
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
    )
    return [InstructorOut.model_validate(u) for u in result.scalars().all()]


@router.get("/{instructor_id}/slots", response_model=list[SlotOut])
async def one_on_one_slots(
    instructor_id: uuid.UUID,
    db: DbSession,
    on_date: Annotated[date, Query(alias="date")],
    duration_minutes: Annotated[int | None, Query(ge=15, le=240)] = None,
) -> list[SlotOut]:
    """Bookable one-to-one slots for a local calendar date.

    Already excludes anything in the past, inside a block, or within the
    one-hour buffer of an existing session — so whatever comes back is bookable
    unless someone beats the caller to it.
    """
    instructor = await db.get(User, instructor_id)
    if instructor is None or not instructor.is_active:
        raise NotFound("Instructor not found.")

    slots = await scheduling.available_slots(
        db, instructor_id, on_date, duration_minutes=duration_minutes
    )
    return [SlotOut(starts_at=s.starts_at, ends_at=s.ends_at) for s in slots]


# ------------------------------------------------------------- time blocking


@router.get("/{instructor_id}/blocks", response_model=list[BlockOut])
async def list_blocks(
    instructor_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
) -> list[BlockOut]:
    if user.id != instructor_id and user.role != UserRole.SUPERUSER:
        raise PermissionDenied("You can only see your own blocked time.")
    blocks = await session_admin.list_blocks(
        db, instructor_id, since=since or utc_now(), until=until
    )
    return [BlockOut.model_validate(b) for b in blocks]


@router.post(
    "/{instructor_id}/blocks", response_model=BlockOut, status_code=status.HTTP_201_CREATED
)
async def create_block(
    instructor_id: uuid.UUID,
    payload: BlockIn,
    db: DbSession,
    user: CurrentUser,
) -> BlockOut:
    """Mark time unavailable so nobody can book it.

    Refuses if live sessions already sit in the range, naming them — quietly
    cancelling someone's booked class as a side effect of "I'm busy Tuesday"
    would be the wrong default.
    """
    instructor = await db.get(User, instructor_id)
    if instructor is None:
        raise NotFound("Instructor not found.")

    block = await session_admin.create_block(
        db,
        instructor=instructor,
        actor=user,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        reason=payload.reason,
        note=payload.note,
    )
    return BlockOut.model_validate(block)


@router.delete("/{instructor_id}/blocks/{block_id}", response_model=Message)
async def delete_block(
    instructor_id: uuid.UUID,
    block_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> Message:
    block = await db.get(InstructorBlock, block_id)
    if block is None or block.instructor_id != instructor_id:
        raise NotFound("Block not found.")
    await session_admin.delete_block(db, block, user)
    return Message(detail="Time unblocked.")


# ------------------------------------------------------- Google connection
#
# Instructors connect their own Google account. The Calendar event — and so the
# Meet link — is created on THEIR calendar, which makes them the actual host of
# the meeting: they can admit people from the lobby, mute, and remove. On a
# shared house account they would join as a powerless participant.


@router.get("/google/connect")
async def google_connect(user: Instructor) -> RedirectResponse:
    if not settings.google_client_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google integration is not configured."
        )
    # `state` carries the user id and a nonce; it is verified on the callback.
    state = f"{user.id}:{secrets.token_urlsafe(16)}"
    return RedirectResponse(google_calendar.build_authorization_url(state))


@router.get("/google/callback")
async def google_callback(
    db: DbSession,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    target = f"{settings.frontend_origin}/instructor"

    if error or not code or not state:
        return RedirectResponse(f"{target}?google=denied")

    try:
        user_id = uuid.UUID(state.split(":", 1)[0])
    except (ValueError, IndexError):
        return RedirectResponse(f"{target}?google=invalid_state")

    user = await db.get(User, user_id)
    if user is None or user.role not in (UserRole.INSTRUCTOR, UserRole.SUPERUSER):
        return RedirectResponse(f"{target}?google=invalid_state")

    try:
        grant = await google_calendar.exchange_code(code)
    except GoogleAPIError:
        return RedirectResponse(f"{target}?google=failed")

    credential = await db.get(GoogleCredential, user_id)
    if credential is None:
        credential = GoogleCredential(user_id=user_id)
        db.add(credential)

    credential.google_email = grant.email
    credential.refresh_token_encrypted = encrypt_secret(grant.refresh_token)
    credential.scopes = grant.scopes
    credential.connected_at = utc_now()
    credential.revoked_at = None
    await db.flush()

    return RedirectResponse(f"{target}?google=connected")


@router.get("/google/status")
async def google_status(user: Instructor, db: DbSession) -> dict:
    credential = await db.get(GoogleCredential, user.id)
    return {
        "connected": credential is not None and credential.is_usable,
        "google_email": credential.google_email if credential else None,
        "connected_at": credential.connected_at if credential else None,
    }


@router.delete("/google/disconnect", response_model=Message)
async def google_disconnect(user: Instructor, db: DbSession) -> Message:
    credential = await db.get(GoogleCredential, user.id)
    if credential is None:
        raise NotFound("No Google account connected.")
    credential.revoked_at = utc_now()
    await db.flush()
    return Message(
        detail="Google disconnected. Sessions you host can no longer get a Meet link."
    )

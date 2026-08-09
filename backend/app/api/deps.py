from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import ACCESS_TOKEN, decode_token
from app.models.enums import UserRole
from app.models.user import User
from app.services import passwords

ACCESS_COOKIE = "shevaani_access"
REFRESH_COOKIE = "shevaani_refresh"


def _extract_token(cookie_value: str | None, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return cookie_value


def token_predates_password_change(payload: dict, user: User) -> bool:
    """A password change signs every other browser out.

    Sessions are stateless JWTs with nothing to revoke, so the check is on the
    way in: anything issued before the last password change is refused. See
    ``services.passwords.token_cutoff`` for why this is a strict ``<``.
    """
    cutoff = passwords.token_cutoff(user)
    if cutoff is None:
        return False
    issued_at = payload.get("iat")
    return issued_at is None or int(issued_at) < cutoff


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    shevaani_access: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = _extract_token(shevaani_access, authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = decode_token(token, ACCESS_TOKEN)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not available")
    if token_predates_password_change(payload, user):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Your password changed. Please sign in again."
        )
    return user


async def get_optional_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    shevaani_access: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    token = _extract_token(shevaani_access, authorization)
    if not token:
        return None
    try:
        payload = decode_token(token, ACCESS_TOKEN)
    except jwt.PyJWTError:
        return None
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active or token_predates_password_change(payload, user):
        return None
    return user


def require_role(*roles: UserRole):
    """Role gate. The frontend guard is UX; this is the one that matters."""

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")
        return user

    return dependency


require_superuser = require_role(UserRole.SUPERUSER)
require_instructor = require_role(UserRole.INSTRUCTOR, UserRole.SUPERUSER)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
Superuser = Annotated[User, Depends(require_superuser)]
Instructor = Annotated[User, Depends(require_instructor)]

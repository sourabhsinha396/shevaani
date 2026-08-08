from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, CurrentUser, DbSession
from app.core.config import settings
from app.core.security import (
    REFRESH_TOKEN,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.enums import PaymentProvider, UserRole
from app.models.user import User
from app.schemas.auth import AuthOut, LoginIn, RegisterIn
from app.schemas.common import Message, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

_SECURE = settings.environment != "development"


def _set_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/",
    )


def _provider_for(country: str | None) -> PaymentProvider | None:
    if not country:
        return None
    return PaymentProvider.RAZORPAY if country.upper() == "IN" else PaymentProvider.STRIPE


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, response: Response, db: DbSession) -> AuthOut:
    email = payload.email.lower()
    existing = await db.execute(select(User.id).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        timezone=payload.timezone,
        billing_country=payload.billing_country,
        preferred_provider=_provider_for(payload.billing_country),
        # Instructor and superuser are assigned out of band — never self-service.
        role=UserRole.LEARNER,
    )
    db.add(user)
    await db.flush()

    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    _set_cookies(response, access, refresh)
    return AuthOut(user=UserOut.model_validate(user), access_token=access, refresh_token=refresh)


@router.post("/login", response_model=AuthOut)
async def login(payload: LoginIn, response: Response, db: DbSession) -> AuthOut:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    # Same error either way — don't reveal which emails exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    _set_cookies(response, access, refresh)
    return AuthOut(user=UserOut.model_validate(user), access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AuthOut)
async def refresh_tokens(
    response: Response,
    db: DbSession,
    shevaani_refresh: Annotated[str | None, Cookie()] = None,
) -> AuthOut:
    if not shevaani_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")
    try:
        payload = decode_token(shevaani_refresh, REFRESH_TOKEN)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not available")

    access = create_access_token(user.id, user.role.value)
    new_refresh = create_refresh_token(user.id)
    _set_cookies(response, access, new_refresh)
    return AuthOut(
        user=UserOut.model_validate(user), access_token=access, refresh_token=new_refresh
    )


@router.post("/logout", response_model=Message)
async def logout(response: Response) -> Message:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return Message(detail="Signed out.")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

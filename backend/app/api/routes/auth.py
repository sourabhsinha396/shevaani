from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    CurrentUser,
    DbSession,
    token_predates_password_change,
)
from app.api.ratelimit import limiter
from app.core.config import settings
from app.core.ratelimit import FORGOT_PASSWORD, LOGIN, REGISTER, VERIFY_EMAIL_SEND
from app.core.security import (
    REFRESH_TOKEN,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.integrations import slack
from app.models.enums import PaymentProvider, UserRole
from app.models.user import User
from app.schemas.auth import (
    AuthOut,
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    RegisterIn,
    ResetPasswordIn,
    VerifyEmailIn,
)
from app.schemas.common import Message, UserOut
from app.services import passwords, verification

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


async def _issue(response: Response, db: AsyncSession, user: User) -> AuthOut:
    """Mint a fresh pair, set the cookies, and return the standard auth payload.

    Tokens are minted *after* the caller has mutated the user, so anything that
    moved ``password_changed_at`` forward has already done so and the tokens
    handed back here survive the check in ``api.deps``.
    """
    await db.flush()
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    _set_cookies(response, access, refresh)
    return AuthOut(user=UserOut.model_validate(user), access_token=access, refresh_token=refresh)


def _provider_for(country: str | None) -> PaymentProvider | None:
    if not country:
        return None
    return PaymentProvider.RAZORPAY if country.upper() == "IN" else PaymentProvider.STRIPE


@router.post(
    "/register",
    response_model=AuthOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limiter("register", REGISTER))],
)
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
    auth = await _issue(response, db, user)

    # Sent, not enforced: signup completes and booking works whether or not the
    # link is ever opened. See services/verification.py for why.
    await verification.send_verification(db, user)

    # Name and country only — the address stays out of Slack.
    await slack.dispatch(
        slack.signup(full_name=user.full_name, country=user.billing_country)
    )
    return auth


@router.post(
    "/login",
    response_model=AuthOut,
    dependencies=[Depends(limiter("login", LOGIN))],
)
async def login(payload: LoginIn, response: Response, db: DbSession) -> AuthOut:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    # Same error either way — don't reveal which emails exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled.")

    if needs_rehash(user.password_hash):
        # A rehash is not a password *change* — leave password_changed_at alone
        # or every login would sign the learner's other browsers out.
        user.password_hash = hash_password(payload.password)

    return await _issue(response, db, user)


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

    # Without this, a password change could be undone by any browser holding an
    # old refresh token — it would simply trade it for a fresh access token and
    # carry on. The refresh endpoint is the one that has to enforce this.
    if token_predates_password_change(payload, user):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Your password changed. Please sign in again."
        )

    return await _issue(response, db, user)


#: One response for every outcome. Whether an address is registered is not
#: something this endpoint is willing to tell an anonymous caller.
_RESET_REQUESTED = (
    "If that address has an account, a reset link is on its way. "
    "It expires in 30 minutes."
)


@router.post(
    "/forgot-password",
    response_model=Message,
    dependencies=[Depends(limiter("forgot-password", FORGOT_PASSWORD))],
)
async def forgot_password(payload: ForgotPasswordIn, request: Request, db: DbSession) -> Message:
    await passwords.request_reset(
        db, payload.email, ip=request.client.host if request.client else None
    )
    return Message(detail=_RESET_REQUESTED)


@router.post("/reset-password", response_model=AuthOut)
async def reset_password(payload: ResetPasswordIn, response: Response, db: DbSession) -> AuthOut:
    """Spend a reset token and sign the browser in.

    Signing in here is deliberate: control of the mailbox has just been proven,
    and bouncing someone to a login form to retype the password they set eight
    seconds ago is friction with no security benefit.
    """
    user = await passwords.reset_password(db, payload.token, payload.password)
    return await _issue(response, db, user)


@router.post("/change-password", response_model=AuthOut)
async def change_password(
    payload: ChangePasswordIn, response: Response, db: DbSession, user: CurrentUser
) -> AuthOut:
    await passwords.change_password(db, user, payload.current_password, payload.new_password)
    # Fresh cookies for this browser; every other one is now holding a token
    # issued before password_changed_at and will be turned away.
    return await _issue(response, db, user)


@router.post(
    "/verify-email/send",
    response_model=Message,
    # There is a 30-second throttle in the service too, but that one is about
    # not annoying the learner. This one is about the endpoint being a way to
    # mail an address repeatedly.
    dependencies=[Depends(limiter("verify-email", VERIFY_EMAIL_SEND))],
)
async def send_email_verification(db: DbSession, user: CurrentUser) -> Message:
    """Ask for a fresh confirmation link for your own address.

    Signed-in only, so there is no oracle to protect here and the response can
    say plainly what happened.
    """
    sent = await verification.send_verification(db, user)
    if not sent:
        return Message(detail="That address is already confirmed.")
    return Message(detail=f"Sent. The link works for {verification.TTL_HOURS} hours.")


@router.post("/verify-email", response_model=UserOut)
async def verify_email(payload: VerifyEmailIn, db: DbSession) -> UserOut:
    """Spend a verification token.

    Unauthenticated on purpose: the link is often opened in whichever browser
    the mail app hands it to, which is frequently not the one holding the
    session. The token is the proof; a cookie would add nothing.
    """
    user = await verification.verify(db, payload.token)
    return UserOut.model_validate(user)


@router.post("/logout", response_model=Message)
async def logout(response: Response) -> Message:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return Message(detail="Signed out.")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

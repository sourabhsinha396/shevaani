from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    LEGACY_REFRESH_COOKIE,
    SESSION_COOKIE,
    CurrentUser,
    DbSession,
)
from app.api.ratelimit import limiter
from app.core.config import settings
from app.core.ratelimit import FORGOT_PASSWORD, LOGIN, REGISTER, VERIFY_EMAIL_SEND
from app.core.security import (
    create_session_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.integrations import google_identity, recaptcha, slack
from app.integrations.google_identity import GoogleAuthError
from app.models.enums import CreditReason, UserRole
from app.models.user import User
from app.schemas.auth import (
    AuthOut,
    ChangePasswordIn,
    ForgotPasswordIn,
    GoogleAuthIn,
    GoogleAuthOut,
    LoginIn,
    RegisterIn,
    ResetPasswordIn,
    VerifyEmailIn,
)
from app.schemas.common import Message, UserOut
from app.services import credits, passwords, referrals, verification
from app.services.scheduling import utc_now

router = APIRouter(prefix="/auth", tags=["auth"])

_SECURE = settings.environment != "development"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        # Matched to the token's own TTL so the browser drops the cookie at the
        # same moment the signature stops verifying. Two different clocks here
        # is how you get a cookie that is sent but always rejected.
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


async def _issue(response: Response, db: AsyncSession, user: User) -> AuthOut:
    """Mint a session token, set the cookie, and return the standard auth payload.

    The token is minted *after* the caller has mutated the user, so anything that
    moved ``password_changed_at`` forward has already done so and the token
    handed back here survives the check in ``api.deps``.
    """
    await db.flush()
    token = create_session_token(user.id, user.role.value)
    _set_session_cookie(response, token)
    return AuthOut(user=UserOut.model_validate(user), access_token=token)


@router.post(
    "/register",
    response_model=AuthOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limiter("register", REGISTER))],
)
async def register(
    payload: RegisterIn, request: Request, response: Response, db: DbSession
) -> AuthOut:
    await recaptcha.require(payload.recaptcha_token, request)
    email = payload.email.lower()
    existing = await db.execute(select(User.id).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        timezone=payload.timezone,
        # Detected by the browser from the same timezone it sends above, not
        # asked for. It no longer decides anything at checkout — the currency
        # does that — so it is kept for support and reporting rather than as a
        # setting the buyer would have to get right at signup.
        billing_country=payload.billing_country,
        # Left unset. Pinning a provider from the signup country outlived its
        # usefulness the moment currency started deciding the gateway, and a
        # stale pin is worse than none: it survives the learner moving country.
        # `services.billing.provider_for` still honours one if support sets it.
        # Instructor and superuser are assigned out of band — never self-service.
        role=UserRole.LEARNER,
        # Everybody gets a link of their own from day one — the referral page
        # never has a "generate" state.
        referral_code=await referrals.unique_code(db),
    )
    db.add(user)
    auth = await _issue(response, db, user)

    # Attribution only: if the browser carried somebody's ?r= code, remember
    # whose. The reward is granted later, at enrolment (first settled payment —
    # see services/referrals.py), so nothing about this signup pays anyone.
    await referrals.record_signup(db, user, payload.referral_code)

    # The welcome credit. Written here rather than by a trigger or a worker so
    # it lands in the same transaction as the account — an account that exists
    # without its credit, or a credit without an account, are both worse than
    # a registration that fails outright and is retried.
    #
    # Once, at creation. Nothing else in the codebase writes SIGNUP_BONUS, so
    # the ledger cannot accumulate a second one for the same person.
    if settings.signup_bonus_credits > 0:
        await credits.grant(
            db,
            user.id,
            settings.signup_bonus_credits,
            CreditReason.SIGNUP_BONUS,
            note="Welcome credit",
        )

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
async def login(
    payload: LoginIn, request: Request, response: Response, db: DbSession
) -> AuthOut:
    await recaptcha.require(payload.recaptcha_token, request)
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


@router.post(
    "/google",
    response_model=GoogleAuthOut,
    # The login bucket, not register's: most presses are returning users, and
    # the expensive part (a Google account with a verified email) is already
    # rate-limited by Google far better than we could.
    dependencies=[Depends(limiter("google", LOGIN))],
)
async def google_auth(payload: GoogleAuthIn, response: Response, db: DbSession) -> GoogleAuthOut:
    """Sign in — or up — with a Google Identity Services credential.

    One endpoint for both, because the browser cannot know which it is: the
    button looks the same to a returning learner and a brand-new one. The
    lookup order is ``google_sub`` first (Google's stable id survives an email
    change), then verified email (which attaches Google to a password account
    made earlier), then a fresh account.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured."
        )

    try:
        identity = await google_identity.verify_id_token(payload.credential)
    except GoogleAuthError:
        # Which check failed is deliberately not echoed to an anonymous caller.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Google sign-in failed. Please try again."
        ) from None

    result = await db.execute(select(User).where(User.google_sub == identity.sub))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == identity.email))
        user = result.scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled.")
        if user.google_sub is None:
            # First Google sign-in on an account made with a password. Safe to
            # attach: Google vouches for the address (email_verified is checked
            # in verify_id_token), which is the same mailbox proof a password
            # reset runs on.
            user.google_sub = identity.sub
        if user.email_verified_at is None:
            user.email_verified_at = utc_now()
        auth = await _issue(response, db, user)
        return GoogleAuthOut(user=auth.user, access_token=auth.access_token, created=False)

    # Nobody yet — a signup, mirroring /register minus everything password:
    # no hash (NULL means Google-only until they set one via forgot-password)
    # and no verification email, since Google has already vouched for the
    # address.
    user = User(
        email=identity.email,
        password_hash=None,
        full_name=identity.full_name,
        timezone=payload.timezone,
        billing_country=payload.billing_country,
        role=UserRole.LEARNER,
        referral_code=await referrals.unique_code(db),
        google_sub=identity.sub,
        email_verified_at=utc_now(),
    )
    db.add(user)
    auth = await _issue(response, db, user)

    await referrals.record_signup(db, user, payload.referral_code)

    if settings.signup_bonus_credits > 0:
        await credits.grant(
            db,
            user.id,
            settings.signup_bonus_credits,
            CreditReason.SIGNUP_BONUS,
            note="Welcome credit",
        )

    await slack.dispatch(
        slack.signup(full_name=user.full_name, country=user.billing_country)
    )
    return GoogleAuthOut(user=auth.user, access_token=auth.access_token, created=True)


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
    await recaptcha.require(payload.recaptcha_token, request)
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
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(LEGACY_REFRESH_COOKIE, path="/")
    return Message(detail="Signed out.")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import UserOut

#: Minimum password length, in one place because it is enforced on three
#: different payloads and a rule that disagrees with itself is not a rule. The
#: frontend mirrors it in `frontend/lib/passwords.ts` for the inline hint; this
#: is the one that actually decides.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

#: What the reCAPTCHA v2 widget put in the form. Optional at the schema level
#: because the whole feature is optional — whether one is *required* is decided
#: in the route against ``settings.recaptcha_configured``, not here.
_RECAPTCHA_FIELD = Field(default=None, max_length=4096)


class SignupContextIn(BaseModel):
    """What the browser knows about a new account regardless of how it signs up.

    Shared between password registration and Google sign-in, so the two kinds
    of signup cannot drift apart on what a timezone or a country may look like.
    """

    timezone: str = "Asia/Kolkata"
    #: ISO-3166 alpha-2, inferred by the browser from the timezone above rather
    #: than asked for. Optional, and no longer load-bearing: currency decides the
    #: gateway and the price, so a wrong or missing country costs nothing.
    billing_country: str | None = Field(default=None, min_length=2, max_length=2)
    #: The ``?r=`` a shared link carried, if the browser kept one. Attribution
    #: only — an unknown or mangled code is ignored, never an error, because a
    #: typo in somebody's WhatsApp message must not block a registration.
    referral_code: str | None = Field(default=None, max_length=32)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @field_validator("billing_country")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class RegisterIn(SignupContextIn):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    full_name: str = Field(min_length=1, max_length=200)
    recaptcha_token: str | None = _RECAPTCHA_FIELD


class GoogleAuthIn(SignupContextIn):
    """One payload for both faces of the Google button — the route decides
    whether this is a sign-in or a signup by looking the identity up, so the
    browser always sends the signup context and it is simply unused when the
    account already exists. No reCAPTCHA: the credential is a signed assertion
    from a signed-in Google account, a higher bar than the checkbox."""

    #: The ID token minted by Google Identity Services in the browser.
    credential: str = Field(min_length=16, max_length=8192)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    recaptcha_token: str | None = _RECAPTCHA_FIELD


class AuthOut(BaseModel):
    user: UserOut
    #: Also set as an httpOnly cookie. Returned for non-browser clients, which
    #: send it as ``Authorization: Bearer``. There is no refresh token — this one
    #: is good for ``SESSION_TTL_DAYS``, after which you sign in again.
    access_token: str


class GoogleAuthOut(AuthOut):
    #: True when this call created the account, so the frontend can route a
    #: fresh signup and a returning sign-in to different places.
    created: bool = False


class ForgotPasswordIn(BaseModel):
    email: EmailStr
    recaptcha_token: str | None = _RECAPTCHA_FIELD


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=16, max_length=512)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=16, max_length=512)

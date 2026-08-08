from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import UserOut


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    timezone: str = "Asia/Kolkata"
    #: ISO-3166 alpha-2. Decides Razorpay vs Stripe at checkout.
    billing_country: str | None = Field(default=None, min_length=2, max_length=2)

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


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthOut(BaseModel):
    user: UserOut
    #: Also set as httpOnly cookies. Returned for non-browser clients.
    access_token: str
    refresh_token: str

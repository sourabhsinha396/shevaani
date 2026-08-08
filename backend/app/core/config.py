from __future__ import annotations

from datetime import time
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_hhmm(value: object) -> time:
    if isinstance(value, time):
        return value
    hour, _, minute = str(value).partition(":")
    return time(int(hour), int(minute or 0))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://shevaani:shevaani@db:5432/shevaani"
    redis_url: str = "redis://redis:6379/0"
    frontend_origin: str = "http://localhost:3000"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    token_encryption_key: str = ""

    # Booking rules
    booking_timezone: str = "Asia/Kolkata"
    one_on_one_window_start: time = time(7, 0)
    one_on_one_window_end: time = time(19, 0)
    one_on_one_buffer_minutes: int = 60
    one_on_one_slot_minutes: int = 60
    booking_hold_minutes: int = 10
    group_autocancel_hours_before: int = 2
    #: Cancel more than this many hours before the start for a full credit refund.
    cancellation_full_refund_hours: int = 12
    join_window_before_minutes: int = 15
    join_window_after_minutes: int = 15

    # Google
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/instructors/google/callback"

    # Payments
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Email
    resend_api_key: str = ""
    email_from: str = "no-reply@shevaani.local"

    @field_validator("one_on_one_window_start", "one_on_one_window_end", mode="before")
    @classmethod
    def _coerce_time(cls, value: object) -> time:
        return _parse_hhmm(value)

    @property
    def tz(self) -> ZoneInfo:
        """The timezone the one-to-one booking window is expressed in."""
        return ZoneInfo(self.booking_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

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
    #: How long a sign-in lasts. One long-lived session token, no refresh flow:
    #: the thing a short TTL usually buys you — bounded damage from a leaked
    #: token — is already covered, because ``api.deps.get_current_user`` reloads
    #: the user from the database on every request. Deactivating an account or
    #: changing a password takes effect on the next request either way, so a
    #: short TTL was only costing learners their session.
    session_ttl_days: int = 30
    token_encryption_key: str = ""
    #: Reset links are short-lived on purpose — they arrive by email, which is
    #: the weakest link in the chain.
    password_reset_ttl_minutes: int = 30

    # Booking rules
    booking_timezone: str = "Asia/Kolkata"
    one_on_one_window_start: time = time(7, 0)
    one_on_one_window_end: time = time(19, 0)
    one_on_one_buffer_minutes: int = 60
    one_on_one_slot_minutes: int = 60
    #: What one session costs. Group and one-to-one are priced the same on
    #: purpose — a learner choosing between them should be choosing a format,
    #: not a price. A single session may still override it (``price_credits``
    #: on the row); this is only the default every path starts from.
    #:
    #: Internal note, not published anywhere: a credit is worth roughly ₹100 to
    #: us, so a session is ~₹200. Pack prices are set against that anchor — see
    #: ``ppp_multipliers`` and the seed in ``app/cli.py`` — and moving this
    #: number without re-checking them changes the real price of a session.
    session_price_credits: int = 2
    #: Credits given once, at registration. Deliberately less than the price of
    #: a session: it is a discount on the first booking, not a free one, so the
    #: account starts with something on it without giving the service away to
    #: anyone who can create an email address. Set to 0 to turn it off.
    signup_bonus_credits: int = 1
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

    # Pricing
    #: The currencies checkout is offered in. USD is the base price list and the
    #: floor everything falls back to, so it is always included whether or not
    #: it is listed here.
    supported_currencies: list[str] = ["USD", "INR", "EUR", "GBP", "AUD"]
    #: Units of the currency per 1 USD. Static, and edited by hand on purpose —
    #: a price that tracks the spot rate charges a different amount than the page
    #: the buyer read ten minutes ago.
    fx_static_rates: dict[str, float] = {"INR": 88.0, "EUR": 0.86, "GBP": 0.74, "AUD": 1.52}
    #: Purchasing power parity: the fraction of the converted price a market is
    #: actually charged. A straight conversion prices Shevaani out of India.
    ppp_multipliers: dict[str, float] = {"INR": 0.65}
    #: Charm rounding, in major units. Nothing sells at ₹1,658.
    currency_round_steps: dict[str, int] = {"INR": 10}

    # Payments
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    #: NOT razorpay_key_secret. Razorpay signs webhooks with a separate secret set
    #: on the webhook itself, and mixing the two fails every signature check.
    razorpay_webhook_secret: str = ""

    # Email — Brevo
    brevo_api_key: str = ""
    email_from: str = "no-reply@shevaani.local"
    email_from_name: str = "Shevaani"
    #: Hours before a session that reminders go out. Each one is a separate mail.
    session_reminder_hours: list[int] = [24, 1]

    # Slack — operational notifications, off unless a webhook is configured.
    slack_webhook_url: str = ""

    # Object storage (S3-compatible: Cloudflare R2, AWS S3, MinIO)
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    #: Where the filesystem fallback writes when no bucket is configured.
    local_storage_dir: str = "/tmp/shevaani-storage"

    # Backups
    backup_prefix: str = "backups/postgres"
    backup_retention_days: int = 30
    backup_hour_utc: int = 18  # 23:30 IST

    # Rate limiting
    rate_limit_enabled: bool = True
    #: Only turn this on when something in front of the app *overwrites*
    #: X-Forwarded-For. If the header is merely appended to, or absent, a caller
    #: can set it themselves and every per-IP limit becomes opt-out.
    trust_proxy_headers: bool = False

    #: Signs the sqladmin cookie at /admin. Separate from JWT_SECRET so rotating
    #: one doesn't invalidate the other; falls back to it when unset.
    admin_session_secret_key: str = ""

    #: Whether /docs, /redoc and /openapi.json are served at all. ``None`` means
    #: "on locally, off everywhere else", which is the answer in every normal
    #: deployment. Setting it True outside local does not make them public —
    #: :mod:`app.api.docs` puts them behind superuser auth.
    expose_api_docs: bool | None = None

    @property
    def admin_session_secret(self) -> str:
        return self.admin_session_secret_key or self.jwt_secret

    @property
    def is_local(self) -> bool:
        """A developer's machine or CI — never a deployed environment.

        Everything that leaks internals (API docs, tracebacks, the schema map)
        keys off this rather than off ``environment != "production"``, so a
        staging box gets the production treatment by default instead of by
        somebody remembering to set a flag.
        """
        return self.environment.lower() in {"development", "local", "test"}

    @property
    def docs_enabled(self) -> bool:
        return self.is_local if self.expose_api_docs is None else self.expose_api_docs

    @property
    def email_configured(self) -> bool:
        """No provider key means outbound mail is logged, not sent — which is what
        makes local development work without an external account."""
        return bool(self.brevo_api_key)

    @property
    def slack_configured(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def storage_configured(self) -> bool:
        """False falls back to the filesystem, so local dev needs no bucket."""
        return bool(self.s3_bucket and self.s3_access_key_id and self.s3_secret_access_key)

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

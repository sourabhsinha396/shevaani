from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import settings

_hasher = PasswordHasher()

#: The only kind of JWT this app issues. Password reset and email verification
#: use database-backed tokens instead (``models/auth.py``), so the claim is not
#: distinguishing between two live schemes — it is there so a token minted by an
#: older build, back when refresh tokens existed, cannot be replayed as a
#: session. Those are valid for up to 30 days from whenever they were issued.
ACCESS_TOKEN = "access"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
    return True


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def _create_token(subject: str, token_type: str, ttl: timedelta, **claims: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
        **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_session_token(user_id: uuid.UUID, role: str) -> str:
    """The whole of the auth scheme: one token, set as one cookie, no refresh.

    ``role`` is informational — every guard reads ``user.role`` from the row it
    just loaded, never the claim, so a role change does not need a new token.
    """
    return _create_token(
        str(user_id),
        ACCESS_TOKEN,
        timedelta(days=settings.session_ttl_days),
        role=role,
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on anything malformed, expired, or of the wrong type."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected a {expected_type} token")
    return payload


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(settings.token_encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    """Used for instructors' Google refresh tokens, which are long-lived credentials."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()

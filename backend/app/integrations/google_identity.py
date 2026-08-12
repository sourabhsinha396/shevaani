"""Verifying Google ID tokens for "Sign in with Google".

The frontend renders Google's Identity Services button, which hands the browser
a signed ID token (a JWT) — there is no redirect and no code exchange, so this
shares nothing with the instructor Calendar flow in ``google_calendar`` beyond
the client id. We verify the token ourselves: signature against Google's
published JWKS, audience against our client id, issuer against Google's two
spellings. Verifying locally rather than calling the tokeninfo endpoint keeps
an HTTP round-trip off every sign-in; the keys rotate rarely, so a module-level
cache refreshed when an unknown ``kid`` shows up is enough.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import jwt

from app.core.config import settings

JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

#: Google signs with either spelling, per their own verification docs.
_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class GoogleAuthError(RuntimeError):
    """Any reason the credential cannot be accepted. The route collapses every
    instance to one 401 — which of the checks failed is nobody's business."""


@dataclass(frozen=True)
class GoogleIdentity:
    #: Google's stable account id. The email can change on their side; this can't.
    sub: str
    email: str
    full_name: str


#: kid -> PyJWK, plus when the set was last fetched. An unknown kid triggers a
#: refetch, but at most once a minute — a stream of forged tokens must not be
#: able to make us hammer Google's cert endpoint.
_keys: dict[str, jwt.PyJWK] = {}
_fetched_at: float = 0.0


async def _key_for(kid: str) -> jwt.PyJWK:
    global _fetched_at

    key = _keys.get(kid)
    if key is None and time.monotonic() - _fetched_at > 60:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(JWKS_URL)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GoogleAuthError(f"Fetching Google's signing keys failed: {exc}") from exc
        _fetched_at = time.monotonic()
        _keys.clear()
        for entry in response.json().get("keys", []):
            _keys[entry["kid"]] = jwt.PyJWK(entry)
        key = _keys.get(kid)

    if key is None:
        raise GoogleAuthError("Credential signed with a key Google does not publish.")
    return key


async def verify_id_token(credential: str) -> GoogleIdentity:
    """Check everything about a GIS credential and distil it to an identity.

    Only verified addresses come back: an unverified email on a Google account
    proves nothing about the mailbox, and both paths that consume this — linking
    to an existing account and creating a fresh one — trust the address.
    """
    try:
        kid = jwt.get_unverified_header(credential).get("kid", "")
        claims = jwt.decode(
            credential,
            (await _key_for(kid)).key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
        )
    except jwt.PyJWTError as exc:
        raise GoogleAuthError(f"Credential rejected: {exc}") from exc

    if claims.get("iss") not in _ISSUERS:
        raise GoogleAuthError("Credential not issued by Google.")

    sub, email = claims.get("sub"), claims.get("email", "").lower()
    if not sub or not email:
        raise GoogleAuthError("Credential carries no usable identity.")
    if not claims.get("email_verified"):
        raise GoogleAuthError("Google reports the email as unverified.")

    return GoogleIdentity(
        sub=sub,
        email=email,
        # Every Google account has a sub and email; a name is not guaranteed.
        full_name=claims.get("name") or email.split("@", 1)[0],
    )

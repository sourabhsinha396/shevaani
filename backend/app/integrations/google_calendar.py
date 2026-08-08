"""Thin async Google Calendar client.

We deliberately avoid ``google-api-python-client`` — it is synchronous, and this
runs inside an async worker. The surface we need is three HTTP calls, so raw
httpx keeps the event loop free and the dependency tree small.

Consumer Gmail accounts cannot use the Meet REST API (``spaces.create`` and
``conferenceRecords`` are Workspace-only), so the Meet link is minted as a side
effect of creating a Calendar event with ``conferenceData.createRequest``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import httpx

from app.core.config import settings

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
CALENDAR_EVENTS = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "openid",
    "email",
]

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class GoogleAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class OAuthGrant:
    refresh_token: str
    access_token: str
    email: str
    scopes: str


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    join_url: str | None
    html_link: str | None


def build_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        # offline + consent is what actually returns a refresh_token. Without
        # prompt=consent, a re-authorising user gets no refresh token back.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def _raise_for_status(response: httpx.Response, action: str) -> None:
    if response.is_success:
        return
    # 4xx other than 429 means the request itself is wrong — retrying won't help.
    retryable = response.status_code == 429 or response.status_code >= 500
    raise GoogleAPIError(
        f"{action} failed ({response.status_code}): {response.text[:500]}",
        status_code=response.status_code,
        retryable=retryable,
    )


async def exchange_code(code: str) -> OAuthGrant:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        _raise_for_status(response, "Token exchange")
        payload = response.json()

        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            raise GoogleAPIError(
                "Google did not return a refresh token. The account may already be "
                "authorised — revoke access at myaccount.google.com and try again.",
                retryable=False,
            )

        access_token = payload["access_token"]
        userinfo = await client.get(
            USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}
        )
        _raise_for_status(userinfo, "Fetching Google profile")

        return OAuthGrant(
            refresh_token=refresh_token,
            access_token=access_token,
            email=userinfo.json().get("email", ""),
            scopes=payload.get("scope", " ".join(SCOPES)),
        )


async def refresh_access_token(refresh_token: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            TOKEN_ENDPOINT,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code == 400:
            # invalid_grant: the user revoked access or changed their password.
            raise GoogleAPIError(
                f"Refresh token rejected: {response.text[:300]}",
                status_code=400,
                retryable=False,
            )
        _raise_for_status(response, "Token refresh")
        return response.json()["access_token"]


def _event_body(
    *,
    summary: str,
    description: str | None,
    starts_at: datetime,
    ends_at: datetime,
    request_id: str | None = None,
) -> dict:
    body: dict = {
        "summary": summary,
        "description": description or "",
        "start": {"dateTime": starts_at.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": ends_at.isoformat(), "timeZone": "UTC"},
        # Learners are not invited as guests — the link is served by our own
        # gated endpoint — but keep this on so a future change can't leak
        # attendee addresses to a room full of strangers.
        "guestsCanSeeOtherGuests": False,
    }
    if request_id:
        body["conferenceData"] = {
            "createRequest": {
                # Deterministic per session: a retry reuses the same conference
                # instead of minting a second one.
                "requestId": request_id,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    return body


async def create_event_with_meet(
    access_token: str,
    *,
    session_id: uuid.UUID,
    summary: str,
    description: str | None,
    starts_at: datetime,
    ends_at: datetime,
    calendar_id: str = "primary",
) -> CalendarEvent:
    url = CALENDAR_EVENTS.format(calendar_id=calendar_id)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            url,
            params={"conferenceDataVersion": 1},
            headers={"Authorization": f"Bearer {access_token}"},
            json=_event_body(
                summary=summary,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
                request_id=f"shevaani-{session_id}",
            ),
        )
        _raise_for_status(response, "Creating calendar event")
        payload = response.json()

    join_url = payload.get("hangoutLink")
    if not join_url:
        for entry in payload.get("conferenceData", {}).get("entryPoints", []):
            if entry.get("entryPointType") == "video":
                join_url = entry.get("uri")
                break

    return CalendarEvent(
        event_id=payload["id"],
        join_url=join_url,
        html_link=payload.get("htmlLink"),
    )


async def update_event_time(
    access_token: str,
    *,
    event_id: str,
    summary: str,
    description: str | None,
    starts_at: datetime,
    ends_at: datetime,
    calendar_id: str = "primary",
) -> None:
    url = f"{CALENDAR_EVENTS.format(calendar_id=calendar_id)}/{event_id}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.patch(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=_event_body(
                summary=summary,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
            ),
        )
        _raise_for_status(response, "Updating calendar event")


async def delete_event(
    access_token: str, *, event_id: str, calendar_id: str = "primary"
) -> None:
    url = f"{CALENDAR_EVENTS.format(calendar_id=calendar_id)}/{event_id}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.delete(
            url, headers={"Authorization": f"Bearer {access_token}"}
        )
        # Already gone is a success for our purposes.
        if response.status_code in (404, 410):
            return
        _raise_for_status(response, "Deleting calendar event")

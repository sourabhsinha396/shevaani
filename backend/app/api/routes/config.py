"""What the frontend is allowed to render.

Public and unauthenticated, because the site chrome asks before it knows who is
looking: the header decides whether to offer 1:1 on a signed-out homepage. That
constraint is the whole contract of this module — see ``SiteConfigOut`` for what
may and may not go on the response.

Writes live in ``routes/admin.py`` with the rest of the superuser surface.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.serializers import build_site_config
from app.schemas.settings import SiteConfigOut
from app.services import site_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=SiteConfigOut)
async def site_config(db: DbSession) -> SiteConfigOut:
    """The feature flags, as the browser should see them.

    Fetched once per render on the frontend and held for the length of its ISR
    window, so a flag flipped in ``/admin/settings`` shows up within about a
    minute rather than instantly. That is the trade for not making every page on
    the site dynamically rendered.

    A flag being on here is not permission to do the thing — it decides what is
    *offered*. The endpoint that performs the action checks the same flag again,
    because this response is public and trivially ignored.
    """
    return build_site_config(await site_settings.load(db))

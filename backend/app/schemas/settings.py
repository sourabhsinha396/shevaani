from __future__ import annotations

from pydantic import BaseModel, create_model

from app.schemas.common import ORMModel


class SiteConfigOut(ORMModel):
    """Every flag the browser is allowed to see.

    This response is public and unauthenticated — the site chrome needs it
    before anyone signs in — so nothing may be added here that is not safe to
    hand to a stranger. Flags only; if an operational setting ever needs an
    admin-only field, it belongs on a separate authenticated response.

    The defaults are the fallback when there is no row at all (see
    ``services/site_settings.load``). They must agree with the column
    ``server_default``s on ``SiteSettings``.
    """

    one_on_one_enabled: bool = True


#: The PATCH body: the same flags, all optional, so a form can send the one
#: switch that moved instead of the whole object — two admins editing different
#: flags at once then don't overwrite each other.
#:
#: Generated rather than written out so a new flag is declared in exactly one
#: place. ``bool | None`` with ``exclude_unset`` on the caller's side is what
#: keeps an explicit ``false`` distinguishable from "not sent".
SiteConfigIn: type[BaseModel] = create_model(
    "SiteConfigIn",
    **{name: (bool | None, None) for name in SiteConfigOut.model_fields},
)

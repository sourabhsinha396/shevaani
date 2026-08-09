"""The API's own documentation surfaces, and who is allowed to see them.

FastAPI serves ``/docs``, ``/redoc`` and ``/openapi.json`` publicly by default.
That is right on a laptop and wrong everywhere else: the schema is a complete,
browsable map of every endpoint, including the join and payment surfaces, and
publishing it hands an attacker the reconnaissance step for free.

So the built-ins are switched off in :mod:`app.main` (``openapi_url=None``) and
re-attached here, which gives three states instead of two:

* local — all three open, exactly as before;
* deployed, default — none of them exist, 404 like any other unknown path;
* deployed with ``EXPOSE_API_DOCS=true`` — all three served, but only to a
  signed-in superuser.

The third state is what makes this liveable. "Turn the docs off in production"
usually decays into someone flipping them back on to debug something and never
flipping them off again; giving that person a gated version means the escape
hatch is not also a hole.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse

from app.api.deps import require_superuser
from app.core.config import settings

OPENAPI_PATH = "/openapi.json"


def mount_docs(app: FastAPI) -> None:
    if not settings.docs_enabled:
        return

    # Locally there is nobody to authenticate against — the database may not even
    # have a superuser yet — so the gate is only applied where it means something.
    guards = [] if settings.is_local else [Depends(require_superuser)]

    @app.get(OPENAPI_PATH, include_in_schema=False, dependencies=guards)
    async def openapi_schema() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False, dependencies=guards)
    async def swagger_ui():  # noqa: ANN202 — returns an HTMLResponse
        return get_swagger_ui_html(openapi_url=OPENAPI_PATH, title=f"{app.title} — docs")

    @app.get("/redoc", include_in_schema=False, dependencies=guards)
    async def redoc():  # noqa: ANN202 — returns an HTMLResponse
        return get_redoc_html(openapi_url=OPENAPI_PATH, title=f"{app.title} — reference")

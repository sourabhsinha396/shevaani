from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin import mount_admin
from app.api.docs import mount_docs
from app.api.routes import (
    admin,
    auth,
    billing,
    bookings,
    config,
    contact,
    instructors,
    sessions,
    webhooks,
)
from app.core.config import settings
from app.services.errors import DomainError
from app.workers import queue

logging.basicConfig(level=logging.INFO)

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await queue.close_pool()


# All three documentation surfaces are switched off here and re-attached by
# `mount_docs` below, which decides whether they exist at all and who may read
# them. Leaving `openapi_url` set would keep the schema public no matter what
# that module does — `docs_url=None` alone hides the viewer, not the map.
app = FastAPI(
    title="Shevaani API",
    version="0.1.0",
    lifespan=lifespan,
    debug=False,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,  # required for the httpOnly auth cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Domain errors carry their own status and a stable machine-readable code."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything that got this far is a bug, and its text is not the caller's business.

    A SQLAlchemy error stringifies to the failing statement, parameters included;
    an httpx one can carry an upstream URL with a token in it. The full traceback
    goes to the server log, where it is useful, and the caller gets a fixed
    sentence. Locally the message is passed through — reading it in the terminal
    is faster than reading it in the log.
    """
    logging.getLogger(__name__).exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    detail = f"{type(exc).__name__}: {exc}" if settings.is_local else "Something went wrong."
    return JSONResponse(status_code=500, content={"detail": detail, "code": "internal_error"})


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness only. Deliberately says nothing about version, environment,
    database reachability or queue depth — an unauthenticated endpoint is not
    where the deployment describes itself."""
    return {"status": "ok"}


app.include_router(config.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(sessions.router, prefix=API_PREFIX)
app.include_router(bookings.router, prefix=API_PREFIX)
app.include_router(instructors.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(contact.router, prefix=API_PREFIX)
app.include_router(billing.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)

# Two different things are called "admin", so be precise about which is which:
#
#   /admin              — sqladmin. The raw data plane: tables, drill-down,
#                         read-only where the schema says it must be.
#   /api/v1/admin       — the JSON API behind the *frontend* admin at
#                         localhost:3000/admin. The operational surface.
#
# The sqladmin one is mounted last so its sub-app can't shadow an API route. It
# carries its own superuser session backend (app/admin/auth.py), re-checked on
# every request — there is no unauthenticated path into it in any environment.
mount_admin(app)

# After the routers, so the generated schema describes the finished app.
mount_docs(app)

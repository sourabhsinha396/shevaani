"""sqladmin, mounted on the API at ``/admin``.

This is the *data plane*: every table, as it actually is, for when something
needs explaining. The operational surface — publishing sessions, retrying a Meet
link, granting credits — is the Next.js admin at ``localhost:3000/admin``, which
talks to ``/api/v1/admin``. Different jobs, deliberately different tools.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqladmin import Admin

from app.admin.auth import SuperuserAuth
from app.admin.views import VIEWS
from app.core.config import settings
from app.core.db import engine


def mount_admin(app: FastAPI) -> Admin:
    admin = Admin(
        app=app,
        engine=engine,
        base_url="/admin",
        title="Shevaani data",
        authentication_backend=SuperuserAuth(
            secret_key=settings.admin_session_secret,
            # The session cookie is a superuser credential — it does not travel
            # over plain HTTP anywhere but a developer's machine.
            https_only=settings.environment == "production",
            same_site="lax",
            max_age=60 * 60 * 8,
        ),
    )
    for view in VIEWS:
        admin.add_view(view)
    return admin

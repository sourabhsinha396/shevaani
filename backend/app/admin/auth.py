"""Session auth for sqladmin.

sqladmin is a server-rendered app, so it can't use the API's bearer tokens — it
needs a cookie session of its own. That session is deliberately *not* the
learner-facing auth cookie: signing into the website must never be a step
towards the data plane.

Only superusers get in, and the check is re-run on every request rather than
trusted from the cookie, so revoking the role logs the person out at once.
"""

from __future__ import annotations

import uuid

from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.core.db import SessionLocal
from app.core.security import verify_password
from app.models.enums import UserRole
from app.models.user import User

SESSION_KEY = "shevaani_admin_user"


class SuperuserAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", "")).strip().lower()
        password = str(form.get("password", ""))

        async with SessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

        # Verify even when there is no such user would be nicer for timing, but
        # the honest simple version is enough here: this endpoint is not public
        # knowledge and the API's login has the same shape.
        if user is None or not user.is_active or user.role != UserRole.SUPERUSER:
            return False
        if not verify_password(password, user.password_hash):
            return False

        request.session.update({SESSION_KEY: str(user.id)})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool | RedirectResponse:
        raw = request.session.get(SESSION_KEY)
        if not raw:
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        try:
            user_id = uuid.UUID(raw)
        except ValueError:
            request.session.clear()
            return RedirectResponse(request.url_for("admin:login"), status_code=302)

        async with SessionLocal() as db:
            user = await db.get(User, user_id)

        # Re-checked per request: losing the role has to take effect immediately,
        # not whenever the cookie happens to expire.
        if user is None or not user.is_active or user.role != UserRole.SUPERUSER:
            request.session.clear()
            return RedirectResponse(request.url_for("admin:login"), status_code=302)
        return True

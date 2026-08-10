from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped


class SiteSettings(Base, Timestamped):
    """Product switches the operator flips without a deploy. Exactly one row.

    The line between this table and ``core/config.py`` is *when* a value has to
    change. Anything the app needs before it can reach the database, or that
    differs per deployment — the database URL, keys, the booking window — is an
    environment variable and always will be. What lives here is the other kind:
    "is this part of the product on today?", answered at runtime by somebody in
    ``/admin/settings`` rather than by a rebuild.

    That distinction is what rules out ``NEXT_PUBLIC_*`` for the frontend half:
    Next inlines those at build time, so hiding a nav item would mean rebuilding
    and redeploying the web image.

    **Typed columns, not a key/value flags table.** A key/value table can add a
    flag with no migration, but nothing reads a flag until frontend code is
    written to consume it — so there is a deploy either way and the saving is
    imaginary. Columns buy real things: proper checkboxes in sqladmin, a typed
    object at both ends, and a flag that is either spelled correctly or fails at
    import rather than silently reading ``False``.

    **Every flag defaults to on.** A missing column value, a missing row, an
    unreachable API — all of them should land on "the site works", never on a
    homepage with the nav quietly emptied out. Off is always something somebody
    chose. See ``services/site_settings.py`` for the missing-row case, which is
    reachable because sqladmin has delete on every table.

    Adding a flag: a column here, a field on ``SiteConfigOut``, a field on the
    frontend ``SiteConfig``, and one entry in the frontend's ``SITE_FLAGS``.
    Nothing else — the admin form and the API are both generated from those.
    """

    __tablename__ = "site_settings"
    #: One row, forever. Without this, "the settings" becomes a question about
    #: which row won, and `load()` would need an ordering to be deterministic.
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # ---- flags ----------------------------------------------------------
    # Off hides 1:1 from the nav *and* refuses the booking. Distinct from "no
    # instructor is free this month", which the availability probe already
    # answers on its own — see routes/instructors.py.
    one_on_one_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

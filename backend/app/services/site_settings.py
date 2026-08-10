"""Reading and writing the single ``site_settings`` row.

Cheap enough to call per request — one primary-key lookup of one narrow row,
which Postgres serves from cache — so there is no cache layer here to go stale
and no invalidation to get wrong. The staleness that does exist is on the
frontend, which holds the config for the length of its ISR window.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import SiteSettings

#: The only id the check constraint permits.
SINGLETON_ID = 1


async def load(db: AsyncSession) -> SiteSettings | None:
    """The settings row, or ``None`` if it has been deleted.

    ``None`` is a real possibility rather than a defensive flourish: sqladmin
    has delete on every table by design. Callers must read it as "every flag at
    its default", which is every flag on — losing this row must not be able to
    take the site's nav away. The next save in ``/admin/settings`` writes it
    back.
    """
    return await db.get(SiteSettings, SINGLETON_ID)


async def is_enabled(db: AsyncSession, flag: str) -> bool:
    """One flag, defaulting to on when the row is missing.

    For the enforcement checks scattered through the services, which care about
    a single switch and not about the shape of the config.
    """
    row = await load(db)
    return True if row is None else bool(getattr(row, flag))


async def update(db: AsyncSession, changes: dict[str, bool]) -> SiteSettings:
    """Apply the flags in ``changes`` and leave the rest alone.

    Recreates the row if it is missing, which is what makes ``/admin/settings``
    the recovery path from a delete in sqladmin. Keys are whatever the request
    schema allowed through — ``SiteConfigIn`` is generated from the flag list,
    so an unknown one cannot reach here.
    """
    row = await load(db)
    if row is None:
        row = SiteSettings(id=SINGLETON_ID)
        db.add(row)
    for flag, value in changes.items():
        setattr(row, flag, value)
    await db.flush()
    # Not optional on the insert path: a flag the caller did not send was filled
    # in by the column's `server_default`, and under asyncio reading an expired
    # attribute lazily raises `MissingGreenlet` rather than fetching it. Refresh
    # while we are still allowed to await.
    await db.refresh(row)
    return row

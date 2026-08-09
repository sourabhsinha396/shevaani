"""Nightly database backup, retention, and restore.

The database holds the credit ledger, booking history and payment records. None
of it is reconstructible from anywhere else — there is no upstream system to
re-import from and no provider who can tell us what somebody's balance was.

**The deliverable is the restore, not the dump.** A dump nobody has ever
restored is a file of unknown value; you find out which on the worst possible
day. So :func:`restore` is part of this module rather than a paragraph in a
runbook, and ``make restore-drill`` runs it end to end against a throwaway
database. See ``docs/BACKUPS.md``.

Format is ``pg_dump -Fc`` (custom): compressed, and restorable selectively with
``pg_restore`` — a plain SQL dump makes "recover just the credit ledger" a text
editing exercise on a very bad morning.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.integrations import storage
from app.services.scheduling import utc_now

logger = logging.getLogger(__name__)


class BackupError(RuntimeError):
    """A backup did not happen. Always worth a human knowing about."""


@dataclass(frozen=True)
class BackupResult:
    key: str
    size_bytes: int
    pruned: int
    destination: str

    def __str__(self) -> str:
        mb = self.size_bytes / (1024 * 1024)
        return f"{self.key} ({mb:.1f} MB) → {self.destination}, pruned {self.pruned}"


def dsn_for_pg_tools(database_url: str | None = None) -> str:
    """``postgresql+asyncpg://…`` is a SQLAlchemy dialect string. libpq has never
    heard of it, and pg_dump will refuse it."""
    url = database_url or settings.database_url
    scheme, _, rest = url.partition("://")
    return f"{scheme.split('+')[0]}://{rest}"


def _key_for(at: datetime) -> str:
    # Sorts chronologically as a string, which is what makes pruning and "what
    # is the newest one" trivial in every S3 browser.
    return f"{settings.backup_prefix}/shevaani-{at:%Y%m%dT%H%M%SZ}.dump"


async def _run(*command: str, action: str) -> None:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        # pg_dump's own message is the only useful diagnostic here — a missing
        # role, a version mismatch, a full disk all look identical otherwise.
        raise BackupError(f"{action} failed ({process.returncode}): {stderr.decode()[:800]}")


async def create(*, now: datetime | None = None) -> BackupResult:
    """Dump, upload, prune. Raises :class:`BackupError` if any step fails."""
    at = now or utc_now()
    key = _key_for(at)
    dsn = dsn_for_pg_tools()

    with tempfile.TemporaryDirectory(prefix="shevaani-backup-") as tmp:
        dump_path = Path(tmp) / "shevaani.dump"
        await _run(
            "pg_dump",
            "--format=custom",
            # Ownership and privileges belong to whatever the restore target is,
            # not to whatever the source happened to have. Without these, a
            # restore into a fresh database fails on roles that do not exist.
            "--no-owner",
            "--no-privileges",
            "--file",
            str(dump_path),
            dsn,
            action="pg_dump",
        )

        size = dump_path.stat().st_size
        if size == 0:
            raise BackupError("pg_dump produced an empty file.")

        await storage.backend().upload_file(
            key, dump_path, content_type="application/octet-stream"
        )

    pruned = await prune(now=at)
    result = BackupResult(
        key=key, size_bytes=size, pruned=pruned, destination=storage.describe()
    )
    logger.info("Backup complete: %s", result)
    return result


async def prune(*, now: datetime | None = None) -> int:
    """Delete dumps past the retention window.

    Deliberately refuses to delete the newest object regardless of age: a
    deployment that stops backing up for longer than the retention period should
    end up with one stale backup, not with none.
    """
    at = now or utc_now()
    cutoff = at - timedelta(days=settings.backup_retention_days)

    objects = sorted(
        await storage.backend().list_keys(settings.backup_prefix), key=lambda o: o.key
    )
    if len(objects) <= 1:
        return 0

    deleted = 0
    for obj in objects[:-1]:  # never the newest
        stamp = _timestamp_from(obj.key)
        if stamp is not None and stamp < cutoff:
            await storage.backend().delete(obj.key)
            deleted += 1
    return deleted


def _timestamp_from(key: str) -> datetime | None:
    """Read the time back out of a key. Anything unparseable is left alone —
    a stray file in the bucket is not something to start deleting on a guess."""
    stem = key.rsplit("/", 1)[-1]
    if not stem.startswith("shevaani-") or not stem.endswith(".dump"):
        return None
    try:
        stamp = datetime.strptime(stem[len("shevaani-") : -len(".dump")], "%Y%m%dT%H%M%SZ")
        return stamp.replace(tzinfo=UTC)
    except ValueError:
        return None


async def latest_key() -> str | None:
    objects = await storage.backend().list_keys(settings.backup_prefix)
    return max((o.key for o in objects), default=None)


async def restore(*, target_dsn: str, key: str | None = None) -> str:
    """Restore a dump into ``target_dsn``.

    ``target_dsn`` is required and never defaulted to the live database. There is
    no sensible default for "which database would you like to overwrite", and the
    one time this is run in anger is the one time a convenient default would be
    catastrophic.

    Used by ``make restore-drill``, which is how we find out the dumps are real
    before we need them to be.
    """
    if urlparse(target_dsn).scheme not in {"postgres", "postgresql"}:
        raise BackupError("target_dsn must be a libpq connection string.")

    chosen = key or await latest_key()
    if chosen is None:
        raise BackupError(f"No backups found under {settings.backup_prefix}.")

    with tempfile.TemporaryDirectory(prefix="shevaani-restore-") as tmp:
        local = Path(tmp) / "shevaani.dump"
        await storage.backend().download_file(chosen, local)
        await _run(
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            # The drill restores into a database that may already have a schema
            # from a previous run; without this the second drill fails on every
            # existing object and looks like a broken backup.
            "--clean",
            "--if-exists",
            "--dbname",
            target_dsn,
            str(local),
            action="pg_restore",
        )

    logger.info("Restored %s into %s", chosen, urlparse(target_dsn).path.lstrip("/"))
    return chosen

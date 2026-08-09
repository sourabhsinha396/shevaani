"""Object storage, S3-compatible.

Two backends behind one interface, chosen by whether a bucket is configured:

* **S3** — Cloudflare R2, AWS S3, MinIO. They differ only in endpoint URL.
* **Filesystem** — the local-development fallback, so ``make up`` needs no cloud
  account and no credentials to run the whole app.

Making the fallback real rather than a stub matters: the backup job is the first
consumer, and a backup path that only works once someone has set up a bucket is
a backup path nobody exercises before they need it.

**Why boto3, and why threads.** Signing SigV4 by hand is a page of code that is
wrong in one subtle way until the day it matters, and every S3-compatible
provider already documents itself against boto3. boto3 is synchronous, so every
call here runs through ``asyncio.to_thread`` — the event loop stays free, which
is the same reason the Calendar client is raw async httpx rather than Google's
blocking SDK. The asymmetry is deliberate: Calendar is three simple HTTP calls,
S3 is a signing protocol.

Nothing in here is on a request path today. Keep it that way if it grows: an
upload belongs in the worker.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int


class StorageBackend(Protocol):
    async def upload_file(
        self, key: str, path: Path, *, content_type: str | None = None
    ) -> str: ...

    async def download_file(self, key: str, path: Path) -> None: ...

    async def list_keys(self, prefix: str) -> list[StoredObject]: ...

    async def delete(self, key: str) -> None: ...

    async def signed_url(self, key: str, *, expires_in: int = 3600) -> str: ...


class S3Storage:
    def _client(self):
        import boto3  # imported lazily so the filesystem path needs no AWS SDK

        return boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    async def upload_file(self, key: str, path: Path, *, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}

        def _run() -> None:
            self._client().upload_file(str(path), settings.s3_bucket, key, ExtraArgs=extra)

        await asyncio.to_thread(_run)
        return key

    async def download_file(self, key: str, path: Path) -> None:
        def _run() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._client().download_file(settings.s3_bucket, key, str(path))

        await asyncio.to_thread(_run)

    async def list_keys(self, prefix: str) -> list[StoredObject]:
        def _run() -> list[StoredObject]:
            paginator = self._client().get_paginator("list_objects_v2")
            found: list[StoredObject] = []
            for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    found.append(StoredObject(key=item["Key"], size=item["Size"]))
            return found

        return await asyncio.to_thread(_run)

    async def delete(self, key: str) -> None:
        def _run() -> None:
            self._client().delete_object(Bucket=settings.s3_bucket, Key=key)

        await asyncio.to_thread(_run)

    async def signed_url(self, key: str, *, expires_in: int = 3600) -> str:
        def _run() -> str:
            return self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket, "Key": key},
                ExpiresIn=expires_in,
            )

        return await asyncio.to_thread(_run)


class FilesystemStorage:
    """The local fallback. Keys become paths under ``LOCAL_STORAGE_DIR``."""

    @property
    def root(self) -> Path:
        return Path(settings.local_storage_dir)

    def _path(self, key: str) -> Path:
        # Keys are ours, not user input, but a traversal here would write
        # anywhere on the worker's filesystem — cheap to refuse outright.
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root.resolve())):
            raise ValueError(f"Refusing key that escapes the storage root: {key!r}")
        return candidate

    async def upload_file(self, key: str, path: Path, *, content_type: str | None = None) -> str:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, path, target)
        return key

    async def download_file(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, self._path(key), path)

    async def list_keys(self, prefix: str) -> list[StoredObject]:
        base = self.root
        if not base.exists():
            return []
        return [
            StoredObject(key=str(p.relative_to(base)), size=p.stat().st_size)
            for p in base.rglob("*")
            if p.is_file() and str(p.relative_to(base)).startswith(prefix)
        ]

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    async def signed_url(self, key: str, *, expires_in: int = 3600) -> str:
        """There is nothing to sign — this is a path on the worker's disk. It is
        returned so callers do not have to branch, and it is useless to anyone
        who is not already on that machine, which is the correct behaviour for a
        development stand-in."""
        return self._path(key).as_uri()


def backend() -> StorageBackend:
    """Whichever backend this environment actually has.

    Resolved per call rather than at import: a deployment that adds credentials
    and restarts the worker gets the real backend without anything else
    changing, and tests can point it at a temporary directory.
    """
    if settings.storage_configured:
        return S3Storage()
    logger.debug("Object storage not configured; using the filesystem fallback.")
    return FilesystemStorage()


def describe() -> str:
    """One line for logs and Slack, so it is never a mystery where a file went."""
    if settings.storage_configured:
        host = settings.s3_endpoint_url or "aws"
        return f"s3://{settings.s3_bucket} ({host})"
    return f"file://{settings.local_storage_dir}"

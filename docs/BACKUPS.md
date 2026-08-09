# Backups and restore

The database holds the credit ledger, booking history and payment records. None
of it can be reconstructed from anywhere else: there is no upstream system to
re-import from, and no payment provider can tell us what somebody's credit
balance was.

**The deliverable is the restore.** A dump nobody has restored is a file of
unknown value, and you find out which one it is on the worst possible day. So
the restore path is code (`app/services/backups.py::restore`), not a paragraph
here, and `make restore-drill` runs it end to end.

## What runs

| | |
|---|---|
| What | `pg_dump --format=custom --no-owner --no-privileges` of the whole database |
| When | Nightly, from the ARQ worker (`backup_database`), at `BACKUP_HOUR_UTC:07` |
| Where | `s3://$S3_BUCKET/$BACKUP_PREFIX/shevaani-<UTC timestamp>.dump` |
| Retention | `BACKUP_RETENTION_DAYS` (default 30), pruned by the same job |
| On failure | Slack, and the ARQ job is recorded as failed. One attempt, not five |

Custom format rather than plain SQL because it is compressed and because
`pg_restore` can pull out a single table — "recover just the credit ledger"
should not be a text-editing exercise on a bad morning.

`--no-owner --no-privileges` because ownership belongs to whatever the restore
target is. Without them, restoring into a fresh database fails on roles that do
not exist there.

Pruning never deletes the newest object, whatever its age. A deployment that
silently stops backing up for longer than the retention window should end up
with one stale backup rather than none.

## Locally, with no bucket

With no S3 credentials the storage adapter falls back to the filesystem
(`LOCAL_STORAGE_DIR`, default `/tmp/shevaani-storage`). Everything below works
unchanged — that is the point of the fallback, since a backup path that only
works once someone has set up a cloud account is a backup path nobody exercises.

## The drill

Run it after any change to the schema, the dump flags, or the storage config —
and on a calendar reminder regardless.

```bash
make restore-drill
```

It drops and recreates a throwaway `shevaani_drill` database, restores the
newest dump into it, and prints row counts for `users`, `sessions`, `bookings`,
`credit_ledger` and `payments`. It never touches the live database — the restore
function refuses to default its target for exactly that reason.

If those counts look like the live system, the backup is real. If the drill
fails, the backup was never a backup, and that is the thing to fix today rather
than the next time it matters.

To rehearse against one specific dump rather than the newest:

```bash
docker compose -f backend/docker-compose.yaml run --rm web python -m app.cli restore-drill --target-dsn postgresql://shevaani:shevaani@db:5432/shevaani_drill --key backups/postgres/shevaani-20260808T183000Z.dump
```

## Restoring for real

Recovery is the drill pointed at a real database instead of a throwaway one.
There is no separate procedure, deliberately — a recovery path that is only
executed during a disaster is one that has never been executed.

1. Stop the API and the worker, so nothing writes while the restore runs.
2. Create the target database, or confirm you intend to overwrite the existing
   one — `pg_restore --clean --if-exists` will drop objects it is about to
   replace.
3. Run `restore-drill` with `--target-dsn` pointing at that database.
4. Check the printed counts against what you expect.
5. Run `alembic upgrade head` — the dump carries the schema as of the dump, and
   the deployed code may be ahead of it.
6. Start the worker, then the API.

Afterwards, take a fresh backup immediately. The restored database is now the
system of record and the dump it came from is one generation behind it.

## What is not covered

* **Point-in-time recovery.** These are nightly snapshots; anything between the
  last dump and the failure is gone. WAL archiving is the answer if that window
  ever becomes unacceptable, and it is a bigger piece of work than this.
* **Redis.** It holds queued jobs and rate-limit counters, all of which are
  reconstructible or expendable. Losing it costs at most a few enqueued
  reminders, which the crons re-derive.
* **Google Calendar events.** Held on instructors' own accounts (PLAN decision
  5), so they survive us entirely.

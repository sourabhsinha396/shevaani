"""Backend-only administration.

Superusers and instructors are created here, never through the API — there is
deliberately no self-service path to either role.

    docker compose run --rm api python -m app.cli seed-superuser
    docker compose run --rm api python -m app.cli create-instructor
    docker compose run --rm api python -m app.cli grant-credits user@example.com 10
    docker compose run --rm api python -m app.cli seed-packs
    docker compose run --rm api python -m app.cli backup-now
    docker compose run --rm api python -m app.cli restore-drill --target-dsn ...
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.billing import CreditPack
from app.models.enums import CreditReason, UserRole
from app.models.user import User
from app.services import backups, credits


class _EmailCheck(BaseModel):
    email: EmailStr


def _validated_email(raw: str) -> str:
    """Validate exactly as the API does.

    Without this the CLI will happily create a superuser whose address the login
    endpoint then rejects — reserved domains like `.local` are the common way to
    end up with an account that can never sign in.
    """
    try:
        return _EmailCheck(email=raw).email.lower()
    except ValidationError as exc:
        reason = exc.errors()[0]["msg"]
        print(f"Invalid email {raw!r}: {reason}", file=sys.stderr)
        raise SystemExit(1) from exc


async def _upsert_user(email: str, full_name: str, password: str, role: UserRole) -> None:
    email = _validated_email(email)
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                role=role,
            )
            db.add(user)
            action = "Created"
        else:
            user.role = role
            user.full_name = full_name or user.full_name
            if password:
                user.password_hash = hash_password(password)
            action = "Updated"

        await db.commit()
        print(f"{action} {role.value}: {email}")


def _prompt_password() -> str:
    password = getpass.getpass("Password: ")
    if len(password) < 10:
        print("Password must be at least 10 characters.", file=sys.stderr)
        raise SystemExit(1)
    if password != getpass.getpass("Confirm: "):
        print("Passwords do not match.", file=sys.stderr)
        raise SystemExit(1)
    return password


#: The price list, in minor units. Kept in step with `frontend/lib/pricing.ts`,
#: which carries the marketing copy for the same slugs — the frontend joins the
#: two on `slug`, so a pack added here without copy there renders bare.
#:
#: Prices are per currency and never converted. ₹ and $ are separate rows.
_PACKS: tuple[tuple[str, str, int, str, int], ...] = (
    ("starter", "Starter", 5, "INR", 49_900),
    ("regular", "Regular", 20, "INR", 169_900),
    ("intensive", "Intensive", 50, "INR", 379_900),
    ("starter", "Starter", 5, "USD", 900),
    ("regular", "Regular", 20, "USD", 2_900),
    ("intensive", "Intensive", 50, "USD", 6_500),
)


async def _seed_packs() -> None:
    """Idempotent. Re-running updates prices on the existing rows.

    Deliberately an update rather than a delete-and-recreate: `payments.pack_id`
    references these, and a re-seed must not orphan purchase history. Prices
    already copied onto a payment row are unaffected either way — that is the
    whole reason they are copied.
    """
    async with SessionLocal() as db:
        for slug, name, credits, currency, amount_minor in _PACKS:
            result = await db.execute(
                select(CreditPack).where(
                    CreditPack.slug == slug, CreditPack.currency == currency
                )
            )
            pack = result.scalar_one_or_none()
            if pack is None:
                db.add(
                    CreditPack(
                        slug=slug,
                        name=name,
                        credits=credits,
                        currency=currency,
                        amount_minor=amount_minor,
                        is_active=True,
                    )
                )
                action = "created"
            else:
                pack.name = name
                pack.credits = credits
                pack.amount_minor = amount_minor
                pack.is_active = True
                action = "updated"
            print(f"{action}: {slug} {currency} {amount_minor} for {credits} credits")
        await db.commit()


async def _grant_credits(email: str, amount: int, note: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == _validated_email(email)))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No such user: {email}", file=sys.stderr)
            raise SystemExit(1)

        await credits.lock_user(db, user.id)
        await credits.grant(
            db,
            user.id,
            amount,
            CreditReason.ADMIN_GRANT if amount > 0 else CreditReason.ADMIN_REVOKE,
            note=note,
        )
        balance = await credits.balance(db, user.id)
        await db.commit()
        print(f"{email}: {amount:+d} credits (balance now {balance})")


async def _backup_now() -> None:
    """Run the nightly backup by hand. Same code path as the cron, on purpose —
    a "manual backup" that takes a different route proves nothing about the
    automatic one."""
    result = await backups.create()
    print(result)


async def _restore_drill(target_dsn: str, key: str | None) -> None:
    """Restore a dump into a throwaway database and report what came back.

    This is the actual deliverable of the backups work. A dump that has never
    been restored is a file, not a backup, and the row counts printed at the end
    are the difference between "the file downloaded" and "the ledger is there".
    """
    restored = await backups.restore(target_dsn=target_dsn, key=key)
    print(f"Restored {restored} into {target_dsn}")

    engine = create_async_engine(f"postgresql+asyncpg://{target_dsn.split('://', 1)[1]}")
    try:
        async with engine.connect() as conn:
            for table in ("users", "sessions", "bookings", "credit_ledger", "payments"):
                count = await conn.scalar(text(f"SELECT count(*) FROM {table}"))  # noqa: S608
                print(f"  {table:<16} {count}")
    finally:
        await engine.dispose()

    print("\nIf those numbers look like the live system, the backup is real.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    roles = (
        ("seed-superuser", UserRole.SUPERUSER),
        ("create-instructor", UserRole.INSTRUCTOR),
    )
    for name, role in roles:
        p = sub.add_parser(name)
        p.add_argument("--email", required=False)
        p.add_argument("--name", required=False, default="")
        p.set_defaults(role=role)

    p_credits = sub.add_parser("grant-credits")
    p_credits.add_argument("email")
    p_credits.add_argument("amount", type=int)
    p_credits.add_argument("--note", default="Granted from the CLI")

    sub.add_parser("seed-packs")
    sub.add_parser("backup-now")

    p_drill = sub.add_parser("restore-drill")
    p_drill.add_argument(
        "--target-dsn",
        required=True,
        help="libpq DSN of a THROWAWAY database. It will be overwritten.",
    )
    p_drill.add_argument("--key", default=None, help="Which dump; default is the newest.")

    args = parser.parse_args()

    if args.command == "grant-credits":
        asyncio.run(_grant_credits(args.email, args.amount, args.note))
        return

    if args.command == "seed-packs":
        asyncio.run(_seed_packs())
        return

    if args.command == "backup-now":
        asyncio.run(_backup_now())
        return

    if args.command == "restore-drill":
        asyncio.run(_restore_drill(args.target_dsn, args.key))
        return

    # Validate before prompting for a password — failing after two password
    # entries is a needlessly annoying way to learn the address is unusable.
    email = _validated_email(args.email or input("Email: ").strip())
    full_name = args.name or input("Full name: ").strip()
    password = _prompt_password()
    asyncio.run(_upsert_user(email, full_name, password, args.role))


if __name__ == "__main__":
    main()

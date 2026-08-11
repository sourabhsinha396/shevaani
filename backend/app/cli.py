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
from app.services import backups, credits, pricing, referrals


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
                # NOT NULL for everyone — staff have referral links too, they
                # just don't advertise them.
                referral_code=await referrals.unique_code(db),
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
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        raise SystemExit(1)
    if password != getpass.getpass("Confirm: "):
        print("Passwords do not match.", file=sys.stderr)
        raise SystemExit(1)
    return password


#: The price list, in US cents. This is the *only* price stored — INR, EUR, GBP
#: and AUD are quoted from it by `app.services.pricing`, so re-pricing a pack is
#: one number here rather than five rows to keep in step.
#:
#: Slugs must match the copy in `frontend/lib/pricing.ts`, which carries the
#: blurb and feature list for the same packs and joins on `slug`; a pack added
#: here without copy there renders bare.
#: Credit counts are **multiples of SESSION_PRICE_CREDITS**. An odd pack strands
#: the remainder forever — credits do not expire, so a leftover half-session is
#: not lost value so much as permanently unusable value, which is worse to look
#: at on a balance. Starter's 2 quote at ₹200, i.e. ₹200 a session: exactly the
#: internal ₹100-a-credit anchor, with Regular and Intensive discounting below it.
#:
#: Sized in sessions — 1, 4, 12 — because that is the unit the buyer is shown and
#: the only one they can act on. The credit column is that number doubled, and
#: nothing outside this file and the ledger should need to know it.
#:
#: Per-session price is deliberately unchanged from the larger packs these
#: replaced ($3.50 / $2.90 / $2.60): the packs got smaller, not dearer.
_PACKS: tuple[tuple[str, str, int, int], ...] = (
    ("starter", "Starter", 2, 350),
    ("regular", "Regular", 8, 1_160),
    ("intensive", "Intensive", 24, 3_120),
)


async def _seed_packs() -> None:
    """Idempotent. Re-running updates prices on the existing rows.

    Deliberately an update rather than a delete-and-recreate: `payments.pack_id`
    references these, and a re-seed must not orphan purchase history. Prices
    already copied onto a payment row are unaffected either way — that is the
    whole reason they are copied.

    Every derived price is printed, not just the USD one. A rate or PPP change
    re-prices four currencies silently otherwise, and "what does this actually
    cost in rupees now" should not require running the conversion by hand.
    """
    async with SessionLocal() as db:
        for slug, name, credits, usd_cents in _PACKS:
            result = await db.execute(select(CreditPack).where(CreditPack.slug == slug))
            pack = result.scalar_one_or_none()
            if pack is None:
                db.add(
                    CreditPack(
                        slug=slug,
                        name=name,
                        credits=credits,
                        usd_cents=usd_cents,
                        is_active=True,
                    )
                )
                action = "created"
            else:
                pack.name = name
                pack.credits = credits
                pack.usd_cents = usd_cents
                pack.is_active = True
                action = "updated"
            quoted = ", ".join(
                f"{code} {minor / 100:,.2f}"
                for code, minor in pricing.localized(usd_cents).items()
            )
            print(f"{action}: {slug} ({credits} credits) — {quoted}")
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

"""Backend-only administration.

Superusers and instructors are created here, never through the API — there is
deliberately no self-service path to either role.

    docker compose run --rm api python -m app.cli seed-superuser
    docker compose run --rm api python -m app.cli create-instructor
    docker compose run --rm api python -m app.cli grant-credits user@example.com 10
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.enums import CreditReason, UserRole
from app.models.user import User
from app.services import credits


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, role in (("seed-superuser", UserRole.SUPERUSER), ("create-instructor", UserRole.INSTRUCTOR)):
        p = sub.add_parser(name)
        p.add_argument("--email", required=False)
        p.add_argument("--name", required=False, default="")
        p.set_defaults(role=role)

    p_credits = sub.add_parser("grant-credits")
    p_credits.add_argument("email")
    p_credits.add_argument("amount", type=int)
    p_credits.add_argument("--note", default="Granted from the CLI")

    args = parser.parse_args()

    if args.command == "grant-credits":
        asyncio.run(_grant_credits(args.email, args.amount, args.note))
        return

    # Validate before prompting for a password — failing after two password
    # entries is a needlessly annoying way to learn the address is unusable.
    email = _validated_email(args.email or input("Email: ").strip())
    full_name = args.name or input("Full name: ").strip()
    password = _prompt_password()
    asyncio.run(_upsert_user(email, full_name, password, args.role))


if __name__ == "__main__":
    main()

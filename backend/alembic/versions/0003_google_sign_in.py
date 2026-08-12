"""google sign-in

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-12

Two changes to ``users``, both for "Sign in with Google":

- ``google_sub`` — Google's stable account id, unique, NULL until the person
  first signs in with Google.
- ``password_hash`` becomes nullable — an account created via Google has no
  password until the owner sets one through the forgot-password flow.

The downgrade backfills an unmatchable argon2-shaped sentinel before
restoring NOT NULL, so it cannot fail on rows Google created. Nobody can log
in with it — it is not a valid hash of anything.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.create_unique_constraint(op.f("uq_users_google_sub"), "users", ["google_sub"])
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_constraint(op.f("uq_users_google_sub"), "users", type_="unique")
    op.drop_column("users", "google_sub")

"""referrals

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-11

Adds the referral program's storage:

- ``users.referral_code`` — the short identifier referral links carry
  (``?r=<code>``). Backfilled for every existing user before it goes NOT NULL,
  so nobody's account predates having a link.
- ``referrals`` — one row per person who arrived through somebody's link.
  Written at signup; ``credited_at`` stays NULL until the referred person
  enrols, which is when the referrer's reward is granted.
- ``referral_bonus`` on the ``credit_reason`` enum. Same shape as 0008: the
  value is added transactionally, nothing here writes a row using it, and the
  downgrade deliberately does not remove it — PostgreSQL has no
  ``DROP VALUE`` and rebuilding the type would rewrite the credit ledger.

The backfill generates codes from the same alphabet ``services.referrals``
uses: lowercase letters and digits with the lookalikes (0/o, 1/l/i) removed,
because these get read out loud and retyped from phone screens.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors app/services/referrals.py — the migration must not import the app.
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_CODE_LENGTH = 8


def _code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))


def upgrade() -> None:
    op.execute("ALTER TYPE credit_reason ADD VALUE IF NOT EXISTS 'referral_bonus'")

    op.add_column("users", sa.Column("referral_code", sa.String(12), nullable=True))

    # Backfill row by row rather than with one UPDATE: the codes must be unique,
    # and SQL's random() has no uniqueness to offer. The set guards against the
    # (astronomically unlikely) in-batch collision; the constraint below is the
    # real enforcement.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM users WHERE referral_code IS NULL")).fetchall()
    used: set[str] = set()
    for (user_id,) in rows:
        code = _code()
        while code in used:
            code = _code()
        used.add(code)
        conn.execute(
            sa.text("UPDATE users SET referral_code = :code WHERE id = :id"),
            {"code": code, "id": user_id},
        )

    op.alter_column("users", "referral_code", nullable=False)
    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])

    op.create_table(
        "referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referrer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referred_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_used", sa.String(32), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_credits", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("referrer_id <> referred_user_id", name="ck_referrals_not_self"),
        sa.ForeignKeyConstraint(
            ["referrer_id"], ["users.id"], name="fk_referrals_referrer_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["referred_user_id"],
            ["users.id"],
            name="fk_referrals_referred_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_referrals"),
        sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])


def downgrade() -> None:
    op.drop_index("ix_referrals_referrer_id", table_name="referrals")
    op.drop_table("referrals")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referral_code")
    # `referral_bonus` stays on the enum — see the module docstring.

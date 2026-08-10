"""usd-base credit packs

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-10

Collapses the per-currency price list to a single USD base price. Before this,
one pack was several rows — a ₹ row and a $ row with the same slug, unique on
``(slug, currency)``. Adding EUR, GBP and AUD would have made that five rows per
pack to keep in step by hand, so the currency column goes and
``app.services.pricing`` quotes the rest from ``usd_cents``.

**Purchase history survives.** ``payments`` copies ``amount_minor`` and
``currency`` off the pack at checkout precisely so it does not depend on the row
still existing or still saying the same thing. Nothing below touches a payment's
amount. The only thing repointed is ``payments.pack_id``, so a rupee purchase
keeps naming the pack it bought instead of being nulled by the FK's ``SET NULL``
when its row is deleted.

**The downgrade is lossy** and says so: the non-USD rows are gone, and coming
back down recreates one USD-priced row per slug rather than the ₹ list that used
to sit beside it. Re-seed after downgrading if the old prices are wanted.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("credit_packs", sa.Column("usd_cents", sa.Integer(), nullable=True))

    # The USD row of each slug is the survivor, and its price becomes the base.
    op.execute("UPDATE credit_packs SET usd_cents = amount_minor WHERE currency = 'USD'")

    # Repoint before deleting: the FK is ON DELETE SET NULL, so dropping the ₹
    # rows first would silently detach every rupee purchase from its pack.
    op.execute(
        """
        UPDATE payments p
           SET pack_id = usd.id
          FROM credit_packs old
          JOIN credit_packs usd ON usd.slug = old.slug AND usd.currency = 'USD'
         WHERE p.pack_id = old.id AND old.currency <> 'USD'
        """
    )
    op.execute("DELETE FROM credit_packs WHERE currency <> 'USD'")
    # A slug that only ever had a non-USD row has no base price and cannot be
    # quoted at all. Deleting beats leaving a row that fails every read.
    op.execute("DELETE FROM credit_packs WHERE usd_cents IS NULL")

    op.alter_column("credit_packs", "usd_cents", nullable=False)
    op.drop_constraint("uq_credit_packs_slug_currency", "credit_packs", type_="unique")
    op.drop_constraint("ck_credit_packs_amount_positive", "credit_packs", type_="check")
    op.drop_column("credit_packs", "amount_minor")
    op.drop_column("credit_packs", "currency")
    op.create_unique_constraint("uq_credit_packs_slug", "credit_packs", ["slug"])
    op.create_check_constraint(
        "ck_credit_packs_usd_cents_positive", "credit_packs", "usd_cents > 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_credit_packs_usd_cents_positive", "credit_packs", type_="check")
    op.drop_constraint("uq_credit_packs_slug", "credit_packs", type_="unique")

    op.add_column("credit_packs", sa.Column("amount_minor", sa.Integer(), nullable=True))
    op.add_column("credit_packs", sa.Column("currency", sa.String(3), nullable=True))
    op.execute("UPDATE credit_packs SET amount_minor = usd_cents, currency = 'USD'")
    op.alter_column("credit_packs", "amount_minor", nullable=False)
    op.alter_column("credit_packs", "currency", nullable=False)

    op.create_unique_constraint(
        "uq_credit_packs_slug_currency", "credit_packs", ["slug", "currency"]
    )
    op.create_check_constraint(
        "ck_credit_packs_amount_positive", "credit_packs", "amount_minor > 0"
    )
    op.drop_column("credit_packs", "usd_cents")

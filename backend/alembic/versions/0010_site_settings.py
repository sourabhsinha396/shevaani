"""site settings — operator-flippable feature flags

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-10

One row holding the switches that decide which parts of the product are on.
Environment variables were the obvious alternative and are wrong for this:
`NEXT_PUBLIC_*` is inlined into the frontend bundle at build time, so hiding a
nav item would mean a rebuild and a redeploy of the web image, and even the
server-side kind needs a restart by somebody with shell access. A row is a
checkbox in an admin that already exists.

The `id = 1` check is what makes "the settings" a well-defined thing rather than
a question about which row won. The row is seeded here so the common path is a
plain primary-key hit; the application still treats a missing row as "every flag
at its default", because sqladmin can delete it.

Defaults are `true` — deliberately, and the same rule applies to every flag
added later. A degraded read has to land on a working site, never on a homepage
with its nav silently emptied out.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "one_on_one_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_site_settings_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_settings")),
    )
    # Seeded, not created on first read: a GET that writes is a GET that needs a
    # transaction and a race story, for a row that is known at migration time.
    op.execute("INSERT INTO site_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("site_settings")

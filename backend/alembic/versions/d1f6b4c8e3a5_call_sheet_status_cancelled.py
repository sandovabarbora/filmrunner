"""call sheet status: cancelled (FR-34)

Revision ID: d1f6b4c8e3a5
Revises: c9e5a3b7d2f4
Create Date: 2026-09-21 13:05:00
"""

from alembic import op

revision = "d1f6b4c8e3a5"
down_revision = "c9e5a3b7d2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE inside a transaction; the value is usable from the next transaction on,
    # which is fine: nothing in this migration writes it.
    op.execute("ALTER TYPE call_sheet_status ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    # Postgres cannot drop an enum value; rows with it would have to be rewritten first. Left as is.
    pass

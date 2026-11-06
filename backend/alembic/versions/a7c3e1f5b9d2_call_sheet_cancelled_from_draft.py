"""remember that a cancelled day was still a draft (FR-222)

Revision ID: a7c3e1f5b9d2
Revises: a7c1e4d9b2f6
Create Date: 2026-11-06 15:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e1f5b9d2"
down_revision = "a7c1e4d9b2f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("call_sheets", sa.Column("cancelled_from_draft", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("call_sheets", "cancelled_from_draft")

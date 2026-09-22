"""actual times per day (FR-65)

Revision ID: f3b8d6e1a9c7
Revises: e2a7c5d9f4b6
Create Date: 2026-09-22 12:10:00
"""

import sqlalchemy as sa
from alembic import op

revision = "f3b8d6e1a9c7"
down_revision = "e2a7c5d9f4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("actual_first_shot", "actual_lunch_out", "actual_lunch_in", "actual_wrap"):
        op.add_column("call_sheets", sa.Column(col, sa.String(length=10), nullable=True))
    op.add_column("call_sheets", sa.Column("actual_note", sa.String(length=500), nullable=True))


def downgrade() -> None:
    for col in ("actual_note", "actual_wrap", "actual_lunch_in", "actual_lunch_out", "actual_first_shot"):
        op.drop_column("call_sheets", col)

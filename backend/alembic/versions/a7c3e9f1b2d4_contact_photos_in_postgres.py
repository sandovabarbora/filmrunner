"""contact photos stored in postgres

Revision ID: a7c3e9f1b2d4
Revises: 1674568dd98c
Create Date: 2026-09-21 11:05:00
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e9f1b2d4"
down_revision = "1674568dd98c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_photos",
        sa.Column("contact_id", sa.Uuid(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("contact_photos")

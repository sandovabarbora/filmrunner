"""contacts.created_by

Revision ID: a7c1e4d9b2f6
Revises: d4f7b0c3e5a6
"""
import sqlalchemy as sa
from alembic import op

revision = "a7c1e4d9b2f6"
down_revision = "d4f7b0c3e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("created_by", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "created_by")

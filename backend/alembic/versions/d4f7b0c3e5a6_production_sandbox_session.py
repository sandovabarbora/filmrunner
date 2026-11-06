"""productions.sandbox_session

Revision ID: d4f7b0c3e5a6
Revises: c3e6a9b2d4f5
"""
import sqlalchemy as sa
from alembic import op

revision = "d4f7b0c3e5a6"
down_revision = "c3e6a9b2d4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("productions", sa.Column("sandbox_session", sa.String(length=32), nullable=True))
    op.create_index("ix_productions_sandbox_session", "productions", ["sandbox_session"])


def downgrade() -> None:
    op.drop_index("ix_productions_sandbox_session", table_name="productions")
    op.drop_column("productions", "sandbox_session")

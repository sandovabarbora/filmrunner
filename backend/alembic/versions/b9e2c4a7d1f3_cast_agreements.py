"""an actor's agreed days, with their evidence (FR-228)

Revision ID: b9e2c4a7d1f3
Revises: a7c3e1f5b9d2
Create Date: 2026-11-11 12:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b9e2c4a7d1f3"
down_revision = "a7c3e1f5b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cast_agreements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cast_member_id", sa.Uuid(), sa.ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("days", postgresql.ARRAY(sa.Date()), nullable=False),
        sa.Column("agreed_by", sa.String(20), nullable=False),
        sa.Column("agreed_via", sa.String(20), nullable=False),
        sa.Column("agreed_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("withdrawn_at", sa.DateTime()),
        sa.Column("withdrawn_by", sa.String(255)),
    )
    op.create_index("ix_cast_agreements_cast_member_id", "cast_agreements", ["cast_member_id"])


def downgrade() -> None:
    op.drop_index("ix_cast_agreements_cast_member_id", table_name="cast_agreements")
    op.drop_table("cast_agreements")

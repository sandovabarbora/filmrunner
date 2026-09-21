"""crew call entries per revision (FR-24)

Revision ID: b8d4f2a6c1e3
Revises: a7c3e9f1b2d4
Create Date: 2026-09-21 11:20:00
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d4f2a6c1e3"
down_revision = "a7c3e9f1b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crew_call_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("call_sheet_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crew_member_id", sa.Uuid(), sa.ForeignKey("crew_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_time", sa.String(length=10), nullable=True),
        sa.Column("pickup_time", sa.String(length=10), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.UniqueConstraint("revision_id", "crew_member_id", name="uq_crew_call_per_revision"),
    )
    op.create_index("ix_crew_call_entries_crew_member_id", "crew_call_entries", ["crew_member_id"])


def downgrade() -> None:
    op.drop_index("ix_crew_call_entries_crew_member_id", table_name="crew_call_entries")
    op.drop_table("crew_call_entries")

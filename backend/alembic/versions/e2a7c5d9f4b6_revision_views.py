"""revision views: who opened which revision (FR-36)

Revision ID: e2a7c5d9f4b6
Revises: d1f6b4c8e3a5
Create Date: 2026-09-21 13:45:00
"""

import sqlalchemy as sa
from alembic import op

revision = "e2a7c5d9f4b6"
down_revision = "d1f6b4c8e3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revision_views",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("call_sheet_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crew_member_id", sa.Uuid(), sa.ForeignKey("crew_members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("revision_id", "crew_member_id", name="uq_revision_view"),
    )
    op.create_index("ix_revision_views_revision_id", "revision_views", ["revision_id"])
    op.create_index("ix_revision_views_crew_member_id", "revision_views", ["crew_member_id"])


def downgrade() -> None:
    op.drop_index("ix_revision_views_crew_member_id", table_name="revision_views")
    op.drop_index("ix_revision_views_revision_id", table_name="revision_views")
    op.drop_table("revision_views")

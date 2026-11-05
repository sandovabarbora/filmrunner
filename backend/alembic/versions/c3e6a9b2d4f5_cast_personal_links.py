"""cast_members.personal_token and revision_views.cast_member_id

Revision ID: c3e6a9b2d4f5
Revises: b2d5f8a1c3e4
Create Date: 2026-11-05 16:00:00.000000

FR-205: an actor gets a personal link like the crew does, with their own
pickup, make-up and on-set times, and their read receipt and confirmation
count on the AD's list. A receipt belongs to exactly one person of either kind.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e6a9b2d4f5'
down_revision: Union[str, None] = 'b2d5f8a1c3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cast_members", sa.Column("personal_token", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE cast_members SET personal_token = replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '') "
        "WHERE personal_token IS NULL"
    )
    op.alter_column("cast_members", "personal_token", nullable=False)
    op.create_unique_constraint("uq_cast_members_personal_token", "cast_members", ["personal_token"])

    op.alter_column("revision_views", "crew_member_id", nullable=True)
    op.add_column("revision_views", sa.Column("cast_member_id", sa.Uuid(), sa.ForeignKey("cast_members.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_revision_views_cast_member_id", "revision_views", ["cast_member_id"])
    op.create_unique_constraint("uq_revision_view_cast", "revision_views", ["revision_id", "cast_member_id"])
    op.create_check_constraint("ck_revision_view_one_person", "revision_views", "(crew_member_id IS NULL) <> (cast_member_id IS NULL)")


def downgrade() -> None:
    op.execute("DELETE FROM revision_views WHERE cast_member_id IS NOT NULL")
    op.drop_constraint("ck_revision_view_one_person", "revision_views", type_="check")
    op.drop_constraint("uq_revision_view_cast", "revision_views", type_="unique")
    op.drop_index("ix_revision_views_cast_member_id", table_name="revision_views")
    op.drop_column("revision_views", "cast_member_id")
    op.alter_column("revision_views", "crew_member_id", nullable=False)
    op.drop_constraint("uq_cast_members_personal_token", "cast_members", type_="unique")
    op.drop_column("cast_members", "personal_token")

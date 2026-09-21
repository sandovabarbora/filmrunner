"""cast call entries follow their cast member (FR-33)

Revision ID: c9e5a3b7d2f4
Revises: b8d4f2a6c1e3
Create Date: 2026-09-21 12:40:00
"""

from alembic import op

revision = "c9e5a3b7d2f4"
down_revision = "b8d4f2a6c1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Same rule as crew_call_entries (FR-24): removing a person from the production drops their
    # per-day entries instead of making the person undeletable once they were ever on a sheet.
    op.drop_constraint("cast_call_entries_cast_member_id_fkey", "cast_call_entries", type_="foreignkey")
    op.create_foreign_key("cast_call_entries_cast_member_id_fkey", "cast_call_entries", "cast_members", ["cast_member_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_cast_call_entries_cast_member_id", "cast_call_entries", ["cast_member_id"])


def downgrade() -> None:
    op.drop_index("ix_cast_call_entries_cast_member_id", table_name="cast_call_entries")
    op.drop_constraint("cast_call_entries_cast_member_id_fkey", "cast_call_entries", type_="foreignkey")
    op.create_foreign_key("cast_call_entries_cast_member_id_fkey", "cast_call_entries", "cast_members", ["cast_member_id"], ["id"])

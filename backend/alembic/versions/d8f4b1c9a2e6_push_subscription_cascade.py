"""push subscriptions cascade on crew member delete (FR-79)

Revision ID: d8f4b1c9a2e6
Revises: 22f098e3dc1d
Create Date: 2026-09-24 11:20:00

"""
from alembic import op

revision = "d8f4b1c9a2e6"
down_revision = "22f098e3dc1d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Same rule as cast_call_entries (FR-33) and crew_call_entries (FR-24):
    # removing a crew member should drop their push subscription, not make
    # the person undeletable because they once turned notifications on.
    # No orphaned rows to worry about: the FK was already enforced (just
    # without ON DELETE), so nothing today references a crew member that
    # no longer exists.
    op.drop_constraint("push_subscriptions_crew_member_id_fkey", "push_subscriptions", type_="foreignkey")
    op.create_foreign_key(
        "push_subscriptions_crew_member_id_fkey", "push_subscriptions", "crew_members", ["crew_member_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("push_subscriptions_crew_member_id_fkey", "push_subscriptions", type_="foreignkey")
    op.create_foreign_key(
        "push_subscriptions_crew_member_id_fkey", "push_subscriptions", "crew_members", ["crew_member_id"], ["id"]
    )

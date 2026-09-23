"""partial unique index: one current revision per call sheet (FR-69)

Revision ID: 22f098e3dc1d
Revises: f3b8d6e1a9c7
Create Date: 2026-09-23 10:20:00
"""

import sqlalchemy as sa
from alembic import op

revision = "22f098e3dc1d"
down_revision = "f3b8d6e1a9c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A plain CREATE UNIQUE INDEX (not CONCURRENTLY) runs inside the
    # migration's transaction and fails loudly, naming the offending
    # call_sheet_id in its DETAIL line, if any existing data already
    # violates the invariant — never a silent row drop.
    op.create_index(
        "uq_call_sheet_revisions_one_current",
        "call_sheet_revisions",
        ["call_sheet_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("uq_call_sheet_revisions_one_current", table_name="call_sheet_revisions")

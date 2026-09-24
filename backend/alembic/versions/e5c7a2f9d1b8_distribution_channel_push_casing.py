"""fix distribution_channel enum: 'push' -> 'PUSH' casing

Revision ID: e5c7a2f9d1b8
Revises: d8f4b1c9a2e6
Create Date: 2026-09-24 15:05:00.000000

FR-86: c2a1f9e7b3d4 added the fourth `distribution_channel` label as
lowercase 'push' (matching DistributionChannel.PUSH's Python *value*),
inconsistent with the original three labels ('EMAIL', 'SMS', 'LINK',
matching the Python member *names*, which is what SQLAlchemy's
Enum(DistributionChannel) sends by default with no values_callable set).
Every write from DistributionChannel.PUSH serializes to "PUSH", which
does not exist in the Postgres enum on a database built through the
migration chain, so it fails with InvalidTextRepresentation.

Alternative considered: add 'PUSH' as a new label and backfill any
existing `channel = 'push'` rows to it, leaving 'push' orphaned in the
enum type (Postgres cannot drop a single enum label). Rejected: renaming
is a single statement, needs no backfill, and any row already logged
against 'push' keeps pointing at the same (renamed) label automatically,
so no data is stranded or duplicated.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5c7a2f9d1b8'
down_revision: Union[str, None] = 'd8f4b1c9a2e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE distribution_channel RENAME VALUE 'push' TO 'PUSH'")


def downgrade() -> None:
    op.execute("ALTER TYPE distribution_channel RENAME VALUE 'PUSH' TO 'push'")

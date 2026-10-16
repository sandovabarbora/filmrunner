"""productions.wrapped_at (FR-181)

Revision ID: 4b1c8a7e2f3d
Revises: 7feea1cfc0e6
Create Date: 2026-10-16 14:30:00.000000

FR-74's own completion note named the blocker this closes: `Production` had
only `created_at`, so the retention report could only measure "row age", not
"time since wrap". This adds `wrapped_at`.

Deviation from this item's own dod, recorded here rather than silently
followed: the dod said to backfill from `updated_at` ("already exists"), but
`Production` has no `updated_at` column — checked directly against
`app/models/production.py`, confirmed empty result. `created_at` is the only
timestamp this table has ever had, so the backfill below uses it, same as
`retention_report.py`'s own pre-existing proxy. This is not a closer
estimate than the proxy it replaces for already-wrapped rows; it only stops
new WRAPPED transitions from needing a proxy going forward.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b1c8a7e2f3d'
down_revision: Union[str, None] = '7feea1cfc0e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('productions', sa.Column('wrapped_at', sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE productions SET wrapped_at = created_at WHERE status = 'WRAPPED' AND wrapped_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column('productions', 'wrapped_at')

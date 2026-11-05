"""revision_views.confirmed_at

Revision ID: a1c4e7f0b2d3
Revises: 7feea1cfc0e6
Create Date: 2026-11-05 14:00:00.000000

FR-202: an opened link is not a read sheet. The crew member's explicit
confirmation lives beside the read receipt, per revision: REV C has to be
confirmed again even if REV B was.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c4e7f0b2d3'
down_revision: Union[str, None] = '7feea1cfc0e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('revision_views', sa.Column('confirmed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('revision_views', 'confirmed_at')

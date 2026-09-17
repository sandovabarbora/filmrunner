"""merge locations and push heads

Revision ID: 1a23c1644d06
Revises: c2a1f9e7b3d4, d353e6845c8e
Create Date: 2026-09-15 16:14:57.801518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a23c1644d06'
down_revision: Union[str, None] = ('c2a1f9e7b3d4', 'd353e6845c8e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

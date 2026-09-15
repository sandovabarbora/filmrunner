"""merge photo head

Revision ID: 1674568dd98c
Revises: 1a23c1644d06, b6a1e5f3d7c2
Create Date: 2026-09-15 16:23:24.543159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1674568dd98c'
down_revision: Union[str, None] = ('1a23c1644d06', 'b6a1e5f3d7c2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""contact photo url

Revision ID: b6a1e5f3d7c2
Revises: 931c2ab3ce65
Create Date: 2026-09-15 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6a1e5f3d7c2'
down_revision: Union[str, None] = '931c2ab3ce65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contacts', sa.Column('photo_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('contacts', 'photo_url')

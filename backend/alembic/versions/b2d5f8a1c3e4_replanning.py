"""call_sheet_revisions.shoot_date and scene_moves

Revision ID: b2d5f8a1c3e4
Revises: a1c4e7f0b2d3
Create Date: 2026-11-05 15:00:00.000000

FR-203: a shoot day can move, so a revision records the date it was published
for (the diff needs the old one), and a scene moved between days is a recorded
fact linking the two revisions, not an unrelated removal and addition.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d5f8a1c3e4'
down_revision: Union[str, None] = 'a1c4e7f0b2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('call_sheet_revisions', sa.Column('shoot_date', sa.Date(), nullable=True))
    op.execute(
        "UPDATE call_sheet_revisions r SET shoot_date = s.shoot_date FROM call_sheets s WHERE r.call_sheet_id = s.id"
    )
    op.create_table(
        'scene_moves',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('scene_number', sa.String(length=20), nullable=False),
        sa.Column('from_revision_id', sa.Uuid(), sa.ForeignKey('call_sheet_revisions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('to_revision_id', sa.Uuid(), sa.ForeignKey('call_sheet_revisions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('scene_moves')
    op.drop_column('call_sheet_revisions', 'shoot_date')

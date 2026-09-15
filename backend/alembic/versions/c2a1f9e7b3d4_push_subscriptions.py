"""push subscriptions, distribution log error and push channel

Revision ID: c2a1f9e7b3d4
Revises: 931c2ab3ce65
Create Date: 2026-09-15 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2a1f9e7b3d4'
down_revision: Union[str, None] = '931c2ab3ce65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'push_subscriptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('crew_member_id', sa.Uuid(), nullable=False),
        sa.Column('endpoint', sa.String(length=1000), nullable=False),
        sa.Column('p256dh', sa.String(length=255), nullable=False),
        sa.Column('auth', sa.String(length=255), nullable=False),
        sa.Column('link_url', sa.String(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['crew_member_id'], ['crew_members.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint'),
    )
    # New enum values cannot be used in the same transaction they are added
    # in on Postgres; this migration only adds the value, nothing writes it.
    op.execute("ALTER TYPE distribution_channel ADD VALUE IF NOT EXISTS 'push'")
    op.add_column('distribution_log', sa.Column('error', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('distribution_log', 'error')
    # Postgres cannot drop a single enum value; downgrading the channel enum
    # itself is deliberately not attempted here (see similar precedent in
    # this repo's migration history for additive enum changes).
    op.drop_table('push_subscriptions')

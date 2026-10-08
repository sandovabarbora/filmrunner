"""push_subscriptions.consecutive_403_count

Revision ID: 7feea1cfc0e6
Revises: e5c7a2f9d1b8
Create Date: 2026-10-06 13:30:00.000000

FR-137: a VAPID key rotation makes every existing subscription's signature
permanently invalid, so the push service 403s it on every future publish —
today indistinguishable in the log from one transient 403. This counter,
reset on any successful send, lets `app/services/notifications.py` tell
"reproducible" from "one-off" without re-deriving it from
`distribution_log` (which has no per-subscription/endpoint column).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7feea1cfc0e6'
down_revision: Union[str, None] = 'e5c7a2f9d1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'push_subscriptions',
        sa.Column('consecutive_403_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('push_subscriptions', 'consecutive_403_count')

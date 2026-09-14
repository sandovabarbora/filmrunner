"""crew member personal token

Revision ID: 931c2ab3ce65
Revises: 5baf4c476bc7
Create Date: 2026-09-14 16:55:13.330085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '931c2ab3ce65'
down_revision: Union[str, None] = '5baf4c476bc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crew_members", sa.Column("personal_token", sa.String(length=64), nullable=True))
    # Backfill existing members with 64 random hex characters (two UUIDs), then lock the column down.
    op.execute(
        "UPDATE crew_members SET personal_token = replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '') "
        "WHERE personal_token IS NULL"
    )
    op.alter_column("crew_members", "personal_token", nullable=False)
    op.create_unique_constraint("uq_crew_members_personal_token", "crew_members", ["personal_token"])


def downgrade() -> None:
    op.drop_constraint("uq_crew_members_personal_token", "crew_members", type_="unique")
    op.drop_column("crew_members", "personal_token")

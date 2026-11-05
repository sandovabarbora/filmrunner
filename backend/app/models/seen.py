"""FR-36: who has opened which revision.

A row per (revision, crew member), written when a crew member's personal
link loads that revision live (not from the phone's cache). This is the
read receipt an AD otherwise chases by phone: "did you get REV B?".
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class RevisionView(Base):
    __tablename__ = "revision_views"
    __table_args__ = (
        UniqueConstraint("revision_id", "crew_member_id", name="uq_revision_view"),
        UniqueConstraint("revision_id", "cast_member_id", name="uq_revision_view_cast"),
        CheckConstraint("(crew_member_id IS NULL) <> (cast_member_id IS NULL)", name="ck_revision_view_one_person"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sheet_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    crew_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crew_members.id", ondelete="CASCADE"), index=True)
    cast_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cast_members.id", ondelete="CASCADE"), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    # FR-202: the person said "I know", not just that a page loaded.
    confirmed_at: Mapped[datetime | None] = mapped_column()

    crew_member = relationship("CrewMember", passive_deletes=True)

"""Who may do what on a production (ADR-005).

A membership is invited by email; the Supabase user id is bound on the
member's first authenticated request, so an AD can invite people before
they have ever signed in.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ProductionRole(str, enum.Enum):
    OWNER = "owner"  # everything, including members
    EDITOR = "editor"  # days, crew, publish
    VIEWER = "viewer"  # read in the editor, no writes


class ProductionMember(Base):
    __tablename__ = "production_members"
    __table_args__ = (UniqueConstraint("production_id", "email", name="uq_production_member_email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    production_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productions.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)  # lowercased
    user_id: Mapped[str | None] = mapped_column(String(255), index=True)  # Supabase `sub`, bound on first request
    role: Mapped[ProductionRole] = mapped_column(Enum(ProductionRole, name="production_role"), nullable=False)
    invited_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    production: Mapped["Production"] = relationship()  # noqa: F821

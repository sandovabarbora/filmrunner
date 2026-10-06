"""Web Push subscriptions (FR-16). See docs/adr/ADR-007-web-push-notifications.md.

Reference:
    - SQLAlchemy 2.0 declarative mapping: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class PushSubscription(Base):
    """One browser/device a crew member opted into notifications from.

    `endpoint` is unique because it *is* the browser's own push-service
    URL — a device that subscribes twice (e.g. after clearing site data)
    gets a new endpoint, not a duplicate of the old one, so re-subscribing
    with the same endpoint is a legitimate key update, not a conflict.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    crew_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crew_members.id", ondelete="CASCADE"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    # The exact personal/crew link this device subscribed from, so a
    # notification's tap-through works without the backend knowing the
    # frontend's deployed origin.
    link_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # FR-137: consecutive 403s from this exact endpoint, reset on any
    # successful send. A VAPID key rotation (INBOX #5's own risk note) makes
    # every old subscription's signature permanently invalid, so it 403s on
    # every future publish — distinct from one transient 403 that clears on
    # the next attempt.
    consecutive_403_count: Mapped[int] = mapped_column(default=0, server_default="0")

    crew_member: Mapped["CrewMember"] = relationship()  # noqa: F821

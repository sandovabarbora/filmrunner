"""CallSheet, CallSheetRevision, ScheduleItem, CastCallEntry, DistributionLog.

See DESIGN.md for why revisions are immutable children rather than an
editable row, and why page counts are stored in eighths.

References:
    - SQLAlchemy 2.0 declarative mapping: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class CallSheetStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class CastStatusCode(str, enum.Enum):
    """Standard industry cast status codes on a call sheet."""

    WORK = "W"
    START_WORK = "SW"
    WORK_FINISH = "WF"
    START_AND_FINISH = "SWF"
    HOLD = "H"
    REHEARSAL = "R"


class DistributionChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    LINK = "link"
    PUSH = "push"


class IntExt(str, enum.Enum):
    INT = "INT"
    EXT = "EXT"


class DayNight(str, enum.Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"


class CallSheet(Base):
    """One call sheet per unit per shoot day. Content lives in revisions."""

    __tablename__ = "call_sheets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    production_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productions.id"), nullable=False)
    shoot_date: Mapped[date] = mapped_column(nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)  # "Day 12"
    day_count: Mapped[int] = mapped_column(Integer, nullable=False)  # "of 30"
    unit_name: Mapped[str] = mapped_column(String(100), default="Main Unit")
    status: Mapped[CallSheetStatus] = mapped_column(
        Enum(CallSheetStatus, name="call_sheet_status"),
        default=CallSheetStatus.DRAFT,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    production: Mapped["Production"] = relationship(back_populates="call_sheets")  # noqa: F821
    revisions: Mapped[list["CallSheetRevision"]] = relationship(
        back_populates="call_sheet", order_by="CallSheetRevision.revision_letter"
    )

    @property
    def current_revision(self) -> "CallSheetRevision | None":
        """The single revision flagged is_current, if any.

        Note: enforced at the application layer (see services/call_sheets.py),
        not by a DB constraint — a partial unique index on
        (call_sheet_id) WHERE is_current would be the stronger version;
        left as a documented TODO rather than added silently.
        TODO: add a partial unique index once the target DB (Postgres) is
        fixed for production, so this invariant can't be violated by a bug.
        """
        return next((r for r in self.revisions if r.is_current), None)


class CallSheetRevision(Base):
    """Immutable snapshot of call-sheet content. A correction adds a row,
    it never edits an existing one — see DESIGN.md."""

    __tablename__ = "call_sheet_revisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    call_sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sheets.id"), nullable=False)
    revision_letter: Mapped[str] = mapped_column(String(1), nullable=False)  # "A", "B", "C"...
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    general_crew_call: Mapped[str | None] = mapped_column(String(10))
    shooting_call: Mapped[str | None] = mapped_column(String(10))
    sunrise: Mapped[str | None] = mapped_column(String(10))
    sunset: Mapped[str | None] = mapped_column(String(10))
    weather_forecast: Mapped[str | None] = mapped_column(String(500))
    safety_notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255))
    # The person running the day on set (usually the 1st AD); shown first in contacts.
    head_of_day_crew_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crew_members.id"))

    call_sheet: Mapped["CallSheet"] = relationship(back_populates="revisions")
    head_of_day: Mapped["CrewMember | None"] = relationship()  # noqa: F821
    schedule_items: Mapped[list["ScheduleItem"]] = relationship(
        back_populates="revision", order_by="ScheduleItem.order_index"
    )
    cast_calls: Mapped[list["CastCallEntry"]] = relationship(back_populates="revision")
    crew_calls: Mapped[list["CrewCallEntry"]] = relationship(back_populates="revision", cascade="all, delete-orphan")
    distribution_log: Mapped[list["DistributionLog"]] = relationship(back_populates="revision")


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sheet_revisions.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_number: Mapped[str] = mapped_column(String(20), nullable=False)  # "42", "42A"
    int_ext: Mapped[IntExt] = mapped_column(Enum(IntExt, name="int_ext"), nullable=False)
    day_night: Mapped[DayNight] = mapped_column(Enum(DayNight, name="day_night"), nullable=False)
    set_description: Mapped[str] = mapped_column(String(500), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"))
    page_count_eighths: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Eighths of a script page, e.g. 19 = 2 3/8 pages"
    )

    revision: Mapped["CallSheetRevision"] = relationship(back_populates="schedule_items")
    location: Mapped["Location | None"] = relationship()  # noqa: F821


class CastCallEntry(Base):
    __tablename__ = "cast_call_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sheet_revisions.id"), nullable=False)
    cast_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cast_members.id"), nullable=False)
    status_code: Mapped[CastStatusCode] = mapped_column(Enum(CastStatusCode, name="cast_status_code"), nullable=False)
    pickup_time: Mapped[str | None] = mapped_column(String(10))
    call_time: Mapped[str | None] = mapped_column(String(10))
    makeup_hair_time: Mapped[str | None] = mapped_column(String(10))
    on_set_time: Mapped[str | None] = mapped_column(String(10))

    revision: Mapped["CallSheetRevision"] = relationship(back_populates="cast_calls")
    cast_member: Mapped["CastMember"] = relationship()  # noqa: F821


class CrewCallEntry(Base):
    """A crew member's own call for one revision (FR-24). Beats the standing time and the general call."""

    __tablename__ = "crew_call_entries"
    __table_args__ = (UniqueConstraint("revision_id", "crew_member_id", name="uq_crew_call_per_revision"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sheet_revisions.id", ondelete="CASCADE"), nullable=False)
    crew_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crew_members.id", ondelete="CASCADE"), nullable=False, index=True)
    call_time: Mapped[str | None] = mapped_column(String(10))
    pickup_time: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(String(300))

    revision: Mapped["CallSheetRevision"] = relationship(back_populates="crew_calls")
    crew_member: Mapped["CrewMember"] = relationship(passive_deletes=True)  # noqa: F821


class DistributionLog(Base):
    """Who a revision was sent to, and whether they've opened it.

    Sending itself (email/SMS provider calls) is out of scope for this
    skeleton — see DESIGN.md. This table lets the application layer answer
    "who hasn't seen today's revision" once sending is wired up.
    """

    __tablename__ = "distribution_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_sheet_revisions.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    channel: Mapped[DistributionChannel] = mapped_column(Enum(DistributionChannel, name="distribution_channel"))
    sent_at: Mapped[datetime | None]
    viewed_at: Mapped[datetime | None]
    # Set when an attempt failed (e.g. a push service rejected the
    # subscription); null means delivered. Lets the AD see who did not
    # get an update instead of assuming everyone did (FR-16 failure case).
    error: Mapped[str | None] = mapped_column(String(500))

    revision: Mapped["CallSheetRevision"] = relationship(back_populates="distribution_log")
    contact: Mapped["Contact"] = relationship()  # noqa: F821

"""Pydantic schemas for CallSheet and its revision content.

A revision is created with its full content in one request (schedule items +
cast calls nested) because that's how an AD actually assembles a call sheet:
as one document, not as independently-created child rows.

Reference: https://docs.pydantic.dev/latest/concepts/models/#nested-models
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.call_sheet import CallSheetStatus, CastStatusCode, DayNight, IntExt
from app.schemas.push import NotificationSummaryRead


class ScheduleItemCreate(BaseModel):
    order_index: int
    scene_number: str
    int_ext: IntExt
    day_night: DayNight
    set_description: str
    location_id: uuid.UUID | None = None
    page_count_eighths: int = Field(ge=0)


class ScheduleItemRead(ScheduleItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class CastCallEntryCreate(BaseModel):
    cast_member_id: uuid.UUID
    status_code: CastStatusCode
    pickup_time: str | None = None
    call_time: str | None = None
    makeup_hair_time: str | None = None
    on_set_time: str | None = None


class CastCallEntryRead(CastCallEntryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class CrewCallEntryCreate(BaseModel):
    crew_member_id: uuid.UUID
    call_time: str | None = None
    pickup_time: str | None = None
    note: str | None = None


class CrewCallEntryRead(CrewCallEntryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class PersonalCallRow(BaseModel):
    """One line of the printed personal-calls table."""

    crew_member_id: uuid.UUID
    name: str
    department: str
    position: str
    call_time: str | None
    pickup_time: str | None
    note: str | None


class CallSheetRevisionCreate(BaseModel):
    """Payload to publish a new revision (initial 'A', or a same-day 'hot
    revision' correcting an already-published one)."""

    general_crew_call: str | None = None
    shooting_call: str | None = None
    sunrise: str | None = None
    sunset: str | None = None
    weather_forecast: str | None = None
    safety_notes: str | None = None
    created_by: str | None = None
    head_of_day_crew_member_id: uuid.UUID | None = None
    schedule_items: list[ScheduleItemCreate] = Field(default_factory=list)
    cast_calls: list[CastCallEntryCreate] = Field(default_factory=list)
    # None = copy the previous revision's entries forward; [] = clear them.
    crew_calls: list[CrewCallEntryCreate] | None = None


class CallSheetRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    call_sheet_id: uuid.UUID
    revision_letter: str
    is_current: bool
    general_crew_call: str | None
    shooting_call: str | None
    sunrise: str | None
    sunset: str | None
    weather_forecast: str | None
    safety_notes: str | None
    created_at: datetime
    created_by: str | None
    head_of_day_crew_member_id: uuid.UUID | None = None
    schedule_items: list[ScheduleItemRead] = []
    cast_calls: list[CastCallEntryRead] = []
    crew_calls: list[CrewCallEntryRead] = []
    # Not a stored field: set by the publish endpoint after sending (FR-16),
    # so the AD sees delivery status without a second request. Absent on a
    # plain GET of an existing revision.
    notifications: NotificationSummaryRead | None = None


class ContactCard(BaseModel):
    """One line of the "who to call" list on the sheet."""

    name: str
    department: str
    position: str
    phone: str | None
    email: str | None
    photo_url: str | None


class PersonalSheet(BaseModel):
    """What a crew member's personal link adds on top of the public sheet (FR-13)."""

    name: str
    department: str
    position: str
    personal_call: str | None
    pickup_time: str | None = None
    note: str | None = None
    department_head: ContactCard | None


class CallSheetContacts(BaseModel):
    """Contacts section of the public sheet: computed, never stored."""

    head_of_day: ContactCard | None
    department_heads: list[ContactCard]
    nearest_hospital: str | None


class CallSheetCreate(BaseModel):
    shoot_date: date
    day_number: int = Field(ge=1)
    day_count: int = Field(ge=1)
    unit_name: str = "Main Unit"
    initial_revision: CallSheetRevisionCreate


class RevisionSummary(BaseModel):
    """The revision this one replaced: enough for "REV B replaces A, issued 06:12"."""

    revision_letter: str
    created_at: datetime


class RevisionChange(BaseModel):
    """One line of "what changed" between the last two revisions (FR-23)."""

    field: str  # crew_call | shooting_call | scene_order | safety_notes | personal_calls
    label: str  # "Crew call"
    before: str | None
    after: str | None


class CallSheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    shoot_date: date
    day_number: int
    day_count: int
    unit_name: str
    status: CallSheetStatus
    created_at: datetime
    current_revision: CallSheetRevisionRead | None = None
    contacts: CallSheetContacts | None = None
    personal_calls: list[PersonalCallRow] = []
    # FR-23: what the current revision replaced and what changed; both empty on a sheet with only REV A.
    previous_revision: RevisionSummary | None = None
    changes: list[RevisionChange] = []


class CrewDayRef(BaseModel):
    """One shoot day as a crew member's stable link lists it (FR-32)."""

    call_sheet_id: uuid.UUID
    shoot_date: date
    day_number: int
    day_count: int
    unit_name: str
    revision_letter: str | None


class CrewNextDay(BaseModel):
    """Where a crew member's one link for the whole shoot should open: the next
    shoot day (today counts), or the last one once the shoot is over."""

    production_name: str
    crew_member_name: str
    call_sheet_id: uuid.UUID | None
    days: list[CrewDayRef]

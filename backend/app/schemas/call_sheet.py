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

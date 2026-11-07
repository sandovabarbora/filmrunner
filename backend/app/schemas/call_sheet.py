"""Pydantic schemas for CallSheet and its revision content.

A revision is created with its full content in one request (schedule items +
cast calls nested) because that's how an AD actually assembles a call sheet:
as one document, not as independently-created child rows.

Reference: https://docs.pydantic.dev/latest/concepts/models/#nested-models
"""

import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.models.call_sheet import CallSheetStatus, CastStatusCode, DayNight, IntExt
from app.schemas.fields import ClockTime, optional_text, text
from app.schemas.push import NotificationSummaryRead

# The database keeps UTC without a zone. Sent as is, a browser reads it as local time: "issued 21:40" for a revision out at 22:40.
UtcDatetime = Annotated[datetime, AfterValidator(lambda d: d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d)]

# Above what any shoot needs, and below the 32-bit Integer columns that would otherwise raise.
_MAX_SEQUENCE = 9999
# 1000 pages, in eighths. A feature script is about 120.
_MAX_PAGE_EIGHTHS = 8000


class ScheduleItemCreate(BaseModel):
    order_index: int = Field(ge=0, le=_MAX_SEQUENCE)
    scene_number: text(20)
    int_ext: IntExt
    day_night: DayNight
    set_description: text(500)
    location_id: uuid.UUID | None = None
    page_count_eighths: int = Field(ge=0, le=_MAX_PAGE_EIGHTHS)


# The *Read models do not extend the *Create ones: stored rows predate the validation and must keep reading back.
class ScheduleItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_index: int
    scene_number: str
    int_ext: IntExt
    day_night: DayNight
    set_description: str
    location_id: uuid.UUID | None = None
    page_count_eighths: int


class CastCallEntryCreate(BaseModel):
    cast_member_id: uuid.UUID
    status_code: CastStatusCode
    pickup_time: ClockTime = None
    call_time: ClockTime = None
    makeup_hair_time: ClockTime = None
    on_set_time: ClockTime = None


class CastCallEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cast_member_id: uuid.UUID
    status_code: CastStatusCode
    pickup_time: str | None = None
    call_time: str | None = None
    makeup_hair_time: str | None = None
    on_set_time: str | None = None


class CrewCallEntryCreate(BaseModel):
    crew_member_id: uuid.UUID
    call_time: ClockTime = None
    pickup_time: ClockTime = None
    note: optional_text(300) = None


class CrewCallEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    crew_member_id: uuid.UUID
    call_time: str | None = None
    pickup_time: str | None = None
    note: str | None = None


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

    general_crew_call: ClockTime = None
    shooting_call: ClockTime = None
    sunrise: ClockTime = None
    sunset: ClockTime = None
    weather_forecast: optional_text(500) = None
    safety_notes: optional_text(2000) = None
    # 247, not the column's 255: the audit label prepends "service:" (routers/call_sheets.py:_audit_label).
    created_by: optional_text(247) = None
    # The revision this edit was made from; a different current one means someone else published in between.
    expected_revision_id: uuid.UUID | None = None
    head_of_day_crew_member_id: uuid.UUID | None = None
    schedule_items: list[ScheduleItemCreate] = Field(default_factory=list)
    # None = copy the previous revision's cast calls forward (same rule as crew_calls); [] = clear them.
    cast_calls: list[CastCallEntryCreate] | None = None
    # None = copy the previous revision's entries forward; [] = clear them.
    crew_calls: list[CrewCallEntryCreate] | None = None

    @field_validator("crew_calls")
    @classmethod
    def _one_entry_per_person(cls, entries: list[CrewCallEntryCreate] | None) -> list[CrewCallEntryCreate] | None:
        # The table's unique constraint would otherwise raise at insert, after the old revision has been retired.
        people = [entry.crew_member_id for entry in entries or []]
        if len(people) != len(set(people)):
            raise ValueError("a person is named more than once in the personal calls")
        return entries


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
    created_at: UtcDatetime
    created_by: str | None
    head_of_day_crew_member_id: uuid.UUID | None = None
    schedule_items: list[ScheduleItemRead] = []
    cast_calls: list[CastCallEntryRead] = []
    crew_calls: list[CrewCallEntryRead] = []


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
    # What this person's own times were on the revision this one replaced; None when they did not move.
    call_before: str | None = None
    pickup_before: str | None = None
    note_changed: bool = False
    # FR-202: which revision this block describes, and whether this person has confirmed that one.
    revision_letter: str | None = None
    confirmed_at: UtcDatetime | None = None
    # FR-205: an actor's link; their times come from the day's cast call, and only someone called today has one.
    is_cast: bool = False
    works_today: bool = True
    makeup_hair_time: str | None = None
    on_set_time: str | None = None
    # FR-204: set when this person last read something older than the previous revision: the diff from there.
    since_letter: str | None = None
    changes_since: list["RevisionChange"] | None = None
    department_head: ContactCard | None


class SheetLocation(BaseModel):
    """Where the day happens (FR-35): one entry per distinct location in schedule order."""

    id: uuid.UUID
    name: str
    address: str | None
    parking_notes: str | None
    nearest_hospital: str | None
    geo_lat: float | None
    geo_lng: float | None
    scene_numbers: list[str]


class CallSheetContacts(BaseModel):
    """Contacts section of the public sheet: computed, never stored."""

    head_of_day: ContactCard | None
    department_heads: list[ContactCard]
    nearest_hospital: str | None


class CallSheetCreate(BaseModel):
    shoot_date: date
    day_number: int = Field(ge=1, le=_MAX_SEQUENCE)
    day_count: int = Field(ge=1, le=_MAX_SEQUENCE)
    unit_name: text(100) = "Main Unit"
    initial_revision: CallSheetRevisionCreate
    # FR-56: a planned day. Kept on the server as status "draft": invisible to the crew, no push,
    # not the target of anyone's stable link, deletable. Publishing later keeps the letter A.
    draft: bool = False


class CastCallRow(BaseModel):
    """A named cast line for the sheet: who, as whom, status and the four times."""

    cast_member_id: uuid.UUID
    name: str
    character_name: str
    status_code: CastStatusCode
    pickup_time: str | None
    call_time: str | None
    makeup_hair_time: str | None
    on_set_time: str | None


class RevisionSummary(BaseModel):
    """The revision this one replaced: enough for "REV B replaces A, issued 06:12"."""

    revision_letter: str
    created_at: UtcDatetime


class RevisionChange(BaseModel):
    """One line of "what changed" between the last two revisions (FR-23)."""

    # shoot_date | crew_call | shooting_call | location | scene_moved_out | scene_moved_in | scenes_added | scenes_removed | scene_detail | scene_order
    # | safety_notes | cast_calls | personal_calls | head_of_day | weather | sunrise | sunset
    field: str
    label: str  # "Crew call"; complete on its own for the push and the AD's history
    before: str | None
    after: str | None
    scenes: list[str] = []  # which scenes this row is about, so the sheet can mark them in the margin
    # FR-203: for a moved scene, the day on the other end, so the sheet can link to it.
    other_call_sheet_id: uuid.UUID | None = None
    other_day_number: int | None = None
    other_date: str | None = None


class OpenedSummary(BaseModel):
    seen: int
    confirmed: int = 0
    total: int
    first_location_name: str | None = None


class Actuals(BaseModel):
    """FR-65: what actually happened on the day; the production's numbers, never the crew's instruction."""

    first_shot: str | None = None
    lunch_out: str | None = None
    lunch_in: str | None = None
    wrap: str | None = None
    note: str | None = None


class ActualsUpdate(BaseModel):
    first_shot: ClockTime = None
    lunch_out: ClockTime = None
    lunch_in: ClockTime = None
    wrap: ClockTime = None
    note: optional_text(500) = None


class HistoryEntry(BaseModel):
    """One line of the day's publish history (FR-50): who published this
    revision, when, what it changed versus the one before, and how many
    crew have opened it. `created_by` is never null on the wire — a
    revision with no recorded author reads as "unknown", not an empty cell."""

    revision_letter: str
    created_at: UtcDatetime
    created_by: str
    changes: list[RevisionChange]
    opened: int
    # FR-78: push delivery now happens in a background task after the publish
    # (or cancel) response is already sent, so it can no longer ride that
    # response (see CallSheetRevisionRead's history). None means no delivery
    # attempt is on record yet for this revision — still in flight, push not
    # configured, or nobody was subscribed; DistributionLog rows appear once
    # the background task commits, typically a second or two later.
    # Cumulative, not "who got told about this publish": a cancellation on
    # the current revision (which does not create a new one) also logs
    # against it, so cancelling right after publishing counts both attempts.
    notifications: NotificationSummaryRead | None = None


class CallSheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    shoot_date: date
    day_number: int
    day_count: int
    unit_name: str
    status: CallSheetStatus
    created_at: UtcDatetime
    production_title: str | None = None  # the sheet's headline; the unit alone says nothing to a freelancer on three shoots
    current_revision: CallSheetRevisionRead | None = None
    contacts: CallSheetContacts | None = None
    personal_calls: list[PersonalCallRow] = []
    cast_calls: list[CastCallRow] = []
    locations: list[SheetLocation] = []
    # FR-43: on the AD's days list only — how many of the crew have opened the current revision.
    opened: OpenedSummary | None = None
    # FR-65: on authenticated reads only; stripped from the public read.
    actuals: Actuals | None = None
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
    status: str = "published"
    # FR-42: enough for "Tomorrow: Day 4 · Thu 24 Sep · crew call 06:30 · Karlštejn" without another request.
    general_crew_call: str | None = None
    first_location_name: str | None = None


class CrewNextDay(BaseModel):
    """Where a crew member's one link for the whole shoot should open: the next
    shoot day (today counts), or the last one once the shoot is over."""

    production_name: str
    crew_member_name: str
    call_sheet_id: uuid.UUID | None
    days: list[CrewDayRef]


class SeenEntry(BaseModel):
    """One crew member in the "who has seen REV B" report (FR-36)."""

    crew_member_id: uuid.UUID
    name: str
    department: str
    position: str
    phone: str | None
    personal_token: str | None  # FR-206: None for a read-only member
    seen_at: UtcDatetime | None
    confirmed_at: UtcDatetime | None = None
    subscribed: bool  # has a push subscription on this production
    is_cast: bool = False  # FR-205; crew_member_id then holds the cast member's id


class MoveSceneRequest(BaseModel):
    """FR-203. `occurrence` tells apart a scene shot in two parts on one day; the letters are what the AD was looking at."""

    scene_number: text(20)
    occurrence: int = Field(default=0, ge=0)
    target_call_sheet_id: uuid.UUID
    expected_revision_letter: text(1)
    expected_target_revision_letter: text(1)


class RescheduleRequest(BaseModel):
    shoot_date: date
    expected_revision_letter: text(1)


class SwapDaysRequest(BaseModel):
    other_call_sheet_id: uuid.UUID
    expected_revision_letter: text(1)
    expected_other_revision_letter: text(1)


class ConfirmRequest(BaseModel):
    revision_letter: text(1) = Field(min_length=1)


class ConfirmResult(BaseModel):
    revision_letter: str
    confirmed_at: UtcDatetime


class SeenReport(BaseModel):
    revision_letter: str
    seen: list[SeenEntry]
    not_seen: list[SeenEntry]

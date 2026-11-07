"""Pydantic schemas for Production, Contact, Location, Crew, Cast.

Reference: https://docs.pydantic.dev/latest/concepts/models/
"""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.production import ProductionStatus
from app.schemas.fields import ClockTime, optional_text, text


# Lengths match the columns, so the *Read models that extend these still read every stored row back.
class ContactCreate(BaseModel):
    name: text(255)
    phone: optional_text(50) = None
    email: optional_text(255) = None


class ContactRead(ContactCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    # Set only via POST/DELETE /contacts/{id}/photo, never accepted on create or PATCH.
    photo_url: str | None = None


class ContactMatch(ContactRead):
    """A contact the caller may reuse (FR-45), with where they last worked so two same names are told apart."""

    last_production_name: str | None = None
    last_position: str | None = None
    # False when the caller only views every film using this person: they can see them but not add them elsewhere.
    can_attach: bool = True


class ProductionCreate(BaseModel):
    name: text(255)
    working_title: optional_text(255) = None
    production_company: optional_text(255) = None
    status: ProductionStatus = ProductionStatus.PREP


class ProductionUpdate(BaseModel):
    """Rename or move the production along its lifecycle (FR-34)."""

    name: optional_text(255) = None
    working_title: optional_text(255) = None
    production_company: optional_text(255) = None
    status: ProductionStatus | None = None


class ProductionRead(ProductionCreate):
    model_config = ConfigDict(from_attributes=True)
    my_role: str | None = None
    permissions: list[str] = []
    id: uuid.UUID


class LocationCreate(BaseModel):
    name: text(255)
    address: optional_text(500) = None
    parking_notes: optional_text(1000) = None
    nearest_hospital: optional_text(500) = None
    geo_lat: float | None = None
    geo_lng: float | None = None


class LocationUpdate(BaseModel):
    name: optional_text(255) = None
    address: optional_text(500) = None
    parking_notes: optional_text(1000) = None
    nearest_hospital: optional_text(500) = None


class LocationRead(LocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    geocoded_display_name: str | None = None


class LocationSuggestion(BaseModel):
    """A weather or nearest-hospital guess the AD accepts or ignores; never
    saved until they explicitly confirm it (ADR-006)."""

    suggestion: str | None


class SunTimes(BaseModel):
    """Computed sunrise and sunset for a location and date (FR-27); both None when the location has no coordinates."""

    sunrise: str | None
    sunset: str | None


class CrewMemberCreate(BaseModel):
    contact_id: uuid.UUID
    department: text(100)
    position: text(100)
    standard_call_time: ClockTime = None
    is_head_of_department: bool = False


# Does not extend the Create model: a stored standing time may predate its validation and must keep reading back.
class CrewMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    contact_id: uuid.UUID
    department: str
    position: str
    standard_call_time: str | None = None
    is_head_of_department: bool = False
    contact: ContactRead
    # The link can confirm a revision on its owner's behalf, so it goes only to those who can edit the crew: None for a viewer.
    personal_token: str | None


class CastMemberCreate(BaseModel):
    contact_id: uuid.UUID
    character_name: text(255)
    standard_pickup_time: ClockTime = None


class CastMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    contact_id: uuid.UUID
    character_name: str
    standard_pickup_time: str | None = None
    contact: ContactRead
    # The link can confirm a revision on its owner's behalf, so it goes only to those who can edit the crew: None for a viewer.
    personal_token: str | None


class CastMemberUpdate(BaseModel):
    character_name: optional_text(255) = None
    standard_pickup_time: ClockTime = None


class MemberCreate(BaseModel):
    email: text(255)
    role: str  # owner | editor | viewer


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    email: str
    user_id: str | None
    role: str
    invited_by: str | None


class ContactUpdate(BaseModel):
    name: optional_text(255) = None
    phone: optional_text(50) = None
    email: optional_text(255) = None


class CrewMemberUpdate(BaseModel):
    department: optional_text(100) = None
    position: optional_text(100) = None
    standard_call_time: ClockTime = None
    is_head_of_department: bool | None = None


class ExtractedContactRead(BaseModel):
    """One candidate from an old call sheet PDF (FR-57); the AD confirms in the same preview as a paste."""

    name: str
    department: str | None
    position: str | None
    phone: str | None
    email: str | None
    warnings: list[str]


class CallSheetPdfExtraction(BaseModel):
    contacts: list[ExtractedContactRead]
    method: str  # "claude" | "heuristics"
    pages: int
    warnings: list[str]

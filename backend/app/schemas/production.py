"""Pydantic schemas for Production, Contact, Location, Crew, Cast.

Reference: https://docs.pydantic.dev/latest/concepts/models/
"""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.production import ProductionStatus


class ContactCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None


class ContactRead(ContactCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    # Set only via POST/DELETE /contacts/{id}/photo, never accepted on create or PATCH.
    photo_url: str | None = None


class ProductionCreate(BaseModel):
    name: str
    working_title: str | None = None
    production_company: str | None = None
    status: ProductionStatus = ProductionStatus.PREP


class ProductionUpdate(BaseModel):
    """Rename or move the production along its lifecycle (FR-34)."""

    name: str | None = None
    working_title: str | None = None
    production_company: str | None = None
    status: ProductionStatus | None = None


class ProductionRead(ProductionCreate):
    model_config = ConfigDict(from_attributes=True)
    my_role: str | None = None
    permissions: list[str] = []
    id: uuid.UUID


class LocationCreate(BaseModel):
    name: str
    address: str | None = None
    parking_notes: str | None = None
    nearest_hospital: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    parking_notes: str | None = None
    nearest_hospital: str | None = None


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
    department: str
    position: str
    standard_call_time: str | None = None
    is_head_of_department: bool = False


class CrewMemberRead(CrewMemberCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    contact: ContactRead
    personal_token: str


class CastMemberCreate(BaseModel):
    contact_id: uuid.UUID
    character_name: str
    standard_pickup_time: str | None = None


class CastMemberRead(CastMemberCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID
    contact: ContactRead


class CastMemberUpdate(BaseModel):
    character_name: str | None = None
    standard_pickup_time: str | None = None


class MemberCreate(BaseModel):
    email: str
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
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CrewMemberUpdate(BaseModel):
    department: str | None = None
    position: str | None = None
    standard_call_time: str | None = None
    is_head_of_department: bool | None = None

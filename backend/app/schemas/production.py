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


class ProductionCreate(BaseModel):
    name: str
    working_title: str | None = None
    production_company: str | None = None
    status: ProductionStatus = ProductionStatus.PREP


class ProductionRead(ProductionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class LocationCreate(BaseModel):
    name: str
    address: str | None = None
    parking_notes: str | None = None
    nearest_hospital: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None


class LocationRead(LocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID


class CrewMemberCreate(BaseModel):
    contact_id: uuid.UUID
    department: str
    position: str
    standard_call_time: str | None = None


class CrewMemberRead(CrewMemberCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID


class CastMemberCreate(BaseModel):
    contact_id: uuid.UUID
    character_name: str
    standard_pickup_time: str | None = None


class CastMemberRead(CastMemberCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    production_id: uuid.UUID

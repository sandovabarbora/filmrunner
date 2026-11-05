"""Production, Location, and Contact models.

References:
    - SQLAlchemy 2.0 declarative mapping: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
"""

import enum
import secrets
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


def new_personal_token() -> str:
    """URL-safe token for a crew member's personal link; 32 bytes of randomness."""
    return secrets.token_urlsafe(32)


class ProductionStatus(str, enum.Enum):
    """Lifecycle status of a production.

    Note: intentionally coarse (3 states). A real production tracks prep
    sub-phases (financing, casting, tech scout...) but that's out of scope
    for the call-sheet skeleton.
    """

    PREP = "prep"
    SHOOTING = "shooting"
    WRAPPED = "wrapped"


class Production(Base):
    __tablename__ = "productions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    working_title: Mapped[str | None] = mapped_column(String(255))
    production_company: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ProductionStatus] = mapped_column(
        Enum(ProductionStatus, name="production_status"),
        default=ProductionStatus.PREP,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    locations: Mapped[list["Location"]] = relationship(back_populates="production")
    crew_members: Mapped[list["CrewMember"]] = relationship(back_populates="production")
    cast_members: Mapped[list["CastMember"]] = relationship(back_populates="production")
    call_sheets: Mapped[list["CallSheet"]] = relationship(back_populates="production")


class Contact(Base):
    """Shared address-book entry.

    Deliberately separate from CrewMember/CastMember: a phone number
    correction should not require touching every call sheet that references
    the person, and the same person can be both crew and reachable via one
    contact record.
    """

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    # Set only via POST /contacts/{id}/photo (Supabase Storage public URL), never by direct PATCH.
    photo_url: Mapped[str | None] = mapped_column(String(500))


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    production_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    parking_notes: Mapped[str | None] = mapped_column(String(1000))
    nearest_hospital: Mapped[str | None] = mapped_column(String(500))
    geo_lat: Mapped[float | None]
    geo_lng: Mapped[float | None]
    # The place name the geocoder resolved `address` to (FR-19/ADR-006), shown
    # next to the address in the editor so a wrong match (common with Czech
    # street names) is visible rather than silently trusted. Not user-edited.
    geocoded_display_name: Mapped[str | None] = mapped_column(String(500))

    production: Mapped["Production"] = relationship(back_populates="locations")


class CrewMember(Base):
    __tablename__ = "crew_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    production_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productions.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    standard_call_time: Mapped[str | None] = mapped_column(String(10))  # "06:30"
    # Heads of department are the "who to call" list on every call sheet.
    is_head_of_department: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Personal link token (FR-13): `?me=<token>` on a crew link shows this member's own call first.
    personal_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=new_personal_token)

    production: Mapped["Production"] = relationship(back_populates="crew_members")
    contact: Mapped["Contact"] = relationship()


class CastMember(Base):
    __tablename__ = "cast_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    production_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productions.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False)
    standard_pickup_time: Mapped[str | None] = mapped_column(String(10))
    personal_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=new_personal_token)

    production: Mapped["Production"] = relationship(back_populates="cast_members")
    contact: Mapped["Contact"] = relationship()


class ContactPhoto(Base):
    """A contact's avatar bytes, stored in Postgres (FR-18): no bucket, no extra key.

    Images are resized to 256 px in the browser before upload, so a row is a
    few tens of kilobytes; the public endpoint serves it with cache headers.
    """

    __tablename__ = "contact_photos"

    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

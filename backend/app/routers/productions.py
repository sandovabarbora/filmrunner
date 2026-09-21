"""Production, Contact, and Location endpoints.

Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/
"""

import logging
import uuid
from datetime import date

from fastapi.responses import Response
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import Principal, require_api_token, require_principal
from app.authz import CREW_EDIT, PRODUCTION_EDIT, PRODUCTION_MANAGE_MEMBERS, PRODUCTION_READ, Access, ROLE_PERMISSIONS, require, resolve_access, resolve_access_or_none, visible_productions
from app.models.call_sheet import CallSheet, CallSheetRevision
from app.models.membership import ProductionMember, ProductionRole
from app.database import get_db
from app.models.production import CastMember, Contact, ContactPhoto, CrewMember, Location, Production
from app.services.storage import ALLOWED_CONTENT_TYPES, MAX_PHOTO_BYTES, PhotoUploadFailed, PhotoUploadNotConfigured, delete_contact_photo, store_contact_photo
from app.schemas.production import (
    ContactUpdate,
    CrewMemberUpdate,
    MemberCreate,
    MemberRead,
    CrewMemberCreate,
    CrewMemberRead,
    ContactCreate,
    ContactRead,
    LocationCreate,
    LocationRead,
    LocationSuggestion,
    SunTimes,
    CastMemberCreate,
    CastMemberRead,
    CastMemberUpdate,
    ProductionUpdate,
    LocationUpdate,
    ProductionCreate,
    ProductionRead,
)
from app.services import geocoding, hospitals, weather
from app.services.astronomy import sunrise_sunset

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_token)])


def _get_production_or_404(db: Session, production_id: uuid.UUID) -> Production:
    production = db.get(Production, production_id)
    if production is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production not found")
    return production


def _with_access(production: Production, role: ProductionRole) -> ProductionRead:
    read = ProductionRead.model_validate(production)
    read.my_role = role.value
    read.permissions = sorted(ROLE_PERMISSIONS[role])
    return read


@router.post("/productions", response_model=ProductionRead, status_code=status.HTTP_201_CREATED)
def create_production(
    payload: ProductionCreate, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)
) -> ProductionRead:
    """Whoever creates a production owns it (service scripts own everything anyway)."""
    production = Production(**payload.model_dump())
    db.add(production)
    db.flush()
    if principal.kind == "user" and principal.email:
        db.add(ProductionMember(production_id=production.id, email=principal.email.lower(), user_id=principal.subject,
                                role=ProductionRole.OWNER, invited_by=principal.email))
    db.commit()
    db.refresh(production)
    logger.info("Created production %s (%s) by %s", production.id, production.name, principal.label)
    return _with_access(production, ProductionRole.OWNER)


@router.get("/productions/{production_id}", response_model=ProductionRead)
def get_production(access: Access = Depends(require(PRODUCTION_READ))) -> ProductionRead:
    return _with_access(access.production, access.role)


@router.patch("/productions/{production_id}", response_model=ProductionRead)
def update_production(payload: ProductionUpdate, db: Session = Depends(get_db), access: Access = Depends(require(PRODUCTION_EDIT))) -> ProductionRead:
    """Rename or move along prep → shooting → wrapped (FR-34). Members and days are untouched."""
    production = access.production
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "name" and (value is None or not value.strip()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A production needs a name")
        setattr(production, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(production)
    return _with_access(production, access.role)


@router.get("/productions", response_model=list[ProductionRead])
def list_productions(db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> list[ProductionRead]:
    """Only productions the caller is a member of; others do not exist as far as they can tell."""
    return [_with_access(p, resolve_access(db, principal, p.id).role) for p in visible_productions(db, principal)]


@router.get("/productions/{production_id}/members", response_model=list[MemberRead])
def list_members(access: Access = Depends(require(PRODUCTION_MANAGE_MEMBERS)), db: Session = Depends(get_db)) -> list[ProductionMember]:
    return list(db.query(ProductionMember).filter(ProductionMember.production_id == access.production.id).order_by(ProductionMember.created_at).all())


@router.post("/productions/{production_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: MemberCreate, access: Access = Depends(require(PRODUCTION_MANAGE_MEMBERS)), db: Session = Depends(get_db)
) -> ProductionMember:
    try:
        role = ProductionRole(payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown role {payload.role!r}") from exc
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="An email address is required")
    existing = db.query(ProductionMember).filter(ProductionMember.production_id == access.production.id, ProductionMember.email == email).first()
    if existing is not None:
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing
    member = ProductionMember(production_id=access.production.id, email=email, role=role, invited_by=access.principal.label)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/productions/{production_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: uuid.UUID, access: Access = Depends(require(PRODUCTION_MANAGE_MEMBERS)), db: Session = Depends(get_db)) -> None:
    member = db.get(ProductionMember, member_id)
    if member is None or member.production_id != access.production.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    owners = db.query(ProductionMember).filter(ProductionMember.production_id == access.production.id, ProductionMember.role == ProductionRole.OWNER).count()
    if member.role == ProductionRole.OWNER and owners <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A production needs at least one owner")
    db.delete(member)
    db.commit()


@router.post("/contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)) -> Contact:
    contact = Contact(**payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _geocode_into(location: Location) -> None:
    """Fill geo_lat/geo_lng/geocoded_display_name from `location.address`.

    A geocoder miss or timeout leaves the coordinate fields untouched (they
    stay editable and empty) rather than raising — ADR-006's "the sheet
    never waits on a third party" rule.
    """
    if not location.address:
        return
    result = geocoding.geocode(location.address)
    if result is None:
        return
    location.geo_lat = result.lat
    location.geo_lng = result.lng
    location.geocoded_display_name = result.display_name


@router.post(
    "/productions/{production_id}/locations",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    production_id: uuid.UUID, payload: LocationCreate, db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT))
) -> Location:
    location = Location(production_id=production_id, **payload.model_dump())
    _geocode_into(location)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/productions/{production_id}/locations", response_model=list[LocationRead])
def list_locations(production_id: uuid.UUID, db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ))) -> list[Location]:
    return list(db.query(Location).filter(Location.production_id == production_id).all())


def _location_of_production_or_404(db: Session, production_id: uuid.UUID, location_id: uuid.UUID) -> Location:
    location = db.get(Location, location_id)
    if location is None or location.production_id != production_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


@router.patch("/productions/{production_id}/locations/{location_id}", response_model=LocationRead)
def update_location(
    production_id: uuid.UUID, location_id: uuid.UUID, payload: LocationUpdate,
    db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT)),
) -> Location:
    location = _location_of_production_or_404(db, production_id, location_id)
    changes = payload.model_dump(exclude_unset=True)
    address_changed = "address" in changes and changes["address"] != location.address
    for field, value in changes.items():
        setattr(location, field, value)
    if address_changed:
        _geocode_into(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/productions/{production_id}/locations/{location_id}/weather-suggestion", response_model=LocationSuggestion)
def get_weather_suggestion(
    production_id: uuid.UUID, location_id: uuid.UUID, shoot_date: date,
    db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ)),
) -> LocationSuggestion:
    location = _location_of_production_or_404(db, production_id, location_id)
    if location.geo_lat is None or location.geo_lng is None:
        return LocationSuggestion(suggestion=None)
    return LocationSuggestion(suggestion=weather.weather_suggestion(location.geo_lat, location.geo_lng, shoot_date))


# --- Cast (FR-33): the people in front of the camera; per-day times live on the revision as cast calls.


@router.post("/productions/{production_id}/cast-members", response_model=CastMemberRead, status_code=status.HTTP_201_CREATED)
def create_cast_member(
    production_id: uuid.UUID, payload: CastMemberCreate, db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT))
) -> CastMember:
    if db.get(Contact, payload.contact_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    actor = CastMember(production_id=production_id, **payload.model_dump())
    db.add(actor)
    db.commit()
    db.refresh(actor)
    return actor


@router.get("/productions/{production_id}/cast-members", response_model=list[CastMemberRead])
def list_cast_members(production_id: uuid.UUID, db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ))) -> list[CastMember]:
    return list(db.query(CastMember).filter(CastMember.production_id == production_id).all())


def _cast_member_of_production_or_404(db: Session, production_id: uuid.UUID, cast_member_id: uuid.UUID) -> CastMember:
    actor = db.get(CastMember, cast_member_id)
    if actor is None or actor.production_id != production_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast member not found")
    return actor


@router.patch("/productions/{production_id}/cast-members/{cast_member_id}", response_model=CastMemberRead)
def update_cast_member(
    production_id: uuid.UUID, cast_member_id: uuid.UUID, payload: CastMemberUpdate,
    db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT)),
) -> CastMember:
    actor = _cast_member_of_production_or_404(db, production_id, cast_member_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(actor, field, value)
    db.commit()
    db.refresh(actor)
    return actor


@router.delete("/productions/{production_id}/cast-members/{cast_member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cast_member(
    production_id: uuid.UUID, cast_member_id: uuid.UUID, db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT))
) -> None:
    """Their per-day cast calls go with them (DB cascade), the same rule as crew (FR-24)."""
    actor = _cast_member_of_production_or_404(db, production_id, cast_member_id)
    db.delete(actor)
    db.commit()


@router.get("/productions/{production_id}/locations/{location_id}/sun", response_model=SunTimes)
def get_sun_times(
    production_id: uuid.UUID, location_id: uuid.UUID, shoot_date: date,
    db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ)),
) -> SunTimes:
    """The same computation publish uses to auto-fill sunrise/sunset (FR-19), so the editor can show it as soon as a location is picked (FR-27)."""
    location = _location_of_production_or_404(db, production_id, location_id)
    if location.geo_lat is None or location.geo_lng is None:
        return SunTimes(sunrise=None, sunset=None)
    rise, sset = sunrise_sunset(location.geo_lat, location.geo_lng, shoot_date)
    return SunTimes(sunrise=rise, sunset=sset)


@router.get("/productions/{production_id}/locations/{location_id}/hospital-suggestion", response_model=LocationSuggestion)
def get_hospital_suggestion(
    production_id: uuid.UUID, location_id: uuid.UUID,
    db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ)),
) -> LocationSuggestion:
    location = _location_of_production_or_404(db, production_id, location_id)
    if location.geo_lat is None or location.geo_lng is None:
        return LocationSuggestion(suggestion=None)
    return LocationSuggestion(suggestion=hospitals.nearest_hospital_suggestion(location.geo_lat, location.geo_lng))


@router.post(
    "/productions/{production_id}/crew-members",
    response_model=CrewMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def create_crew_member(
    production_id: uuid.UUID, payload: CrewMemberCreate, db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT))
) -> CrewMember:
    if db.get(Contact, payload.contact_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    member = CrewMember(production_id=production_id, **payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/productions/{production_id}/crew-members", response_model=list[CrewMemberRead])
def list_crew_members(production_id: uuid.UUID, db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ))) -> list[CrewMember]:
    return list(db.query(CrewMember).filter(CrewMember.production_id == production_id).all())


def _member_of_production_or_404(db: Session, production_id: uuid.UUID, member_id: uuid.UUID) -> CrewMember:
    member = db.get(CrewMember, member_id)
    if member is None or member.production_id != production_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crew member not found")
    return member


@router.patch("/productions/{production_id}/crew-members/{member_id}", response_model=CrewMemberRead)
def update_crew_member(
    production_id: uuid.UUID, member_id: uuid.UUID, payload: CrewMemberUpdate,
    db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT)),
) -> CrewMember:
    """Edit role fields; the personal link token is never rotated here."""
    member = _member_of_production_or_404(db, production_id, member_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/productions/{production_id}/crew-members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_crew_member(
    production_id: uuid.UUID, member_id: uuid.UUID, db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT))
) -> None:
    member = _member_of_production_or_404(db, production_id, member_id)
    heads_day = (
        db.query(CallSheet)
        .join(CallSheetRevision, CallSheetRevision.call_sheet_id == CallSheet.id)
        .filter(CallSheetRevision.head_of_day_crew_member_id == member.id)
        .order_by(CallSheet.shoot_date)
        .first()
    )
    if heads_day is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{member.contact.name} is head of day on Day {heads_day.day_number} ({heads_day.shoot_date}); pick another head of day first",
        )
    db.delete(member)
    db.commit()


def _require_contact_edit(db: Session, principal: Principal, contact_id: uuid.UUID) -> None:
    """Contacts are shared rows; editing one needs crew:edit on a production that has this person in its crew."""
    if principal.kind == "service":
        return
    production_ids = {m.production_id for m in db.query(CrewMember).filter(CrewMember.contact_id == contact_id)}
    allowed = any(CREW_EDIT in resolve_access_or_none(db, principal, pid) for pid in production_ids)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot edit this contact: no production you edit has this person in its crew")


@router.patch("/contacts/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: uuid.UUID, payload: ContactUpdate, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)
) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    _require_contact_edit(db, principal, contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/contacts/{contact_id}/photo", response_model=ContactRead)
async def upload_contact_photo_endpoint(
    contact_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db), principal: Principal = Depends(require_principal)
) -> Contact:
    """Crew avatar upload (FR-18, gated on the `avatars` Supabase Storage bucket).

    Decoupled from `PATCH /contacts/{id}`: a failed upload (415/413/503/502)
    never touches the contact's other fields, so an editor's name/phone/etc.
    change already saved stays saved.
    """
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    _require_contact_edit(db, principal, contact_id)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Photo must be JPEG or PNG, got {file.content_type!r}")
    data = await file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Photo is larger than {MAX_PHOTO_BYTES // 1000} KB; resize before uploading")
    try:
        contact.photo_url = store_contact_photo(db, str(contact_id), data, file.content_type)
    except PhotoUploadNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except PhotoUploadFailed as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contacts/{contact_id}/photo", response_model=ContactRead)
def remove_contact_photo(
    contact_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)
) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    _require_contact_edit(db, principal, contact_id)
    contact.photo_url = None
    delete_contact_photo(db, contact_id)
    db.commit()
    db.refresh(contact)
    return contact


public_router = APIRouter()  # unauthenticated: the crew's phones load avatars from the sheet


@public_router.get("/public/contacts/{contact_id}/photo")
def get_contact_photo_public(contact_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Serve a stored avatar. Cacheable for a day; the URL's ?v= changes on re-upload."""
    row = db.get(ContactPhoto, contact_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo")
    return Response(content=row.data, media_type=row.content_type, headers={"Cache-Control": "public, max-age=86400"})

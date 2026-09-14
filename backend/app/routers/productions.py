"""Production, Contact, and Location endpoints.

Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import Principal, require_api_token, require_principal
from app.authz import CREW_EDIT, PRODUCTION_MANAGE_MEMBERS, PRODUCTION_READ, Access, ROLE_PERMISSIONS, require, resolve_access, visible_productions
from app.models.membership import ProductionMember, ProductionRole
from app.database import get_db
from app.models.production import Contact, CrewMember, Location, Production
from app.schemas.production import (
    MemberCreate,
    MemberRead,
    CrewMemberCreate,
    CrewMemberRead,
    ContactCreate,
    ContactRead,
    LocationCreate,
    LocationRead,
    ProductionCreate,
    ProductionRead,
)

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


@router.post(
    "/productions/{production_id}/locations",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    production_id: uuid.UUID, payload: LocationCreate, db: Session = Depends(get_db), _: Access = Depends(require(CREW_EDIT))
) -> Location:
    location = Location(production_id=production_id, **payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/productions/{production_id}/locations", response_model=list[LocationRead])
def list_locations(production_id: uuid.UUID, db: Session = Depends(get_db), _: Access = Depends(require(PRODUCTION_READ))) -> list[Location]:
    return list(db.query(Location).filter(Location.production_id == production_id).all())


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

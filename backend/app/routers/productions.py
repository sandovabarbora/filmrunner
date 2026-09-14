"""Production, Contact, and Location endpoints.

Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_token
from app.database import get_db
from app.models.production import Contact, CrewMember, Location, Production
from app.schemas.production import (
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


@router.post("/productions", response_model=ProductionRead, status_code=status.HTTP_201_CREATED)
def create_production(payload: ProductionCreate, db: Session = Depends(get_db)) -> Production:
    production = Production(**payload.model_dump())
    db.add(production)
    db.commit()
    db.refresh(production)
    logger.info("Created production %s (%s)", production.id, production.name)
    return production


@router.get("/productions/{production_id}", response_model=ProductionRead)
def get_production(production_id: uuid.UUID, db: Session = Depends(get_db)) -> Production:
    return _get_production_or_404(db, production_id)


@router.get("/productions", response_model=list[ProductionRead])
def list_productions(db: Session = Depends(get_db)) -> list[Production]:
    return list(db.query(Production).order_by(Production.created_at.desc()).all())


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
    production_id: uuid.UUID, payload: LocationCreate, db: Session = Depends(get_db)
) -> Location:
    _get_production_or_404(db, production_id)
    location = Location(production_id=production_id, **payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/productions/{production_id}/locations", response_model=list[LocationRead])
def list_locations(production_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Location]:
    _get_production_or_404(db, production_id)
    return list(db.query(Location).filter(Location.production_id == production_id).all())


@router.post(
    "/productions/{production_id}/crew-members",
    response_model=CrewMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def create_crew_member(
    production_id: uuid.UUID, payload: CrewMemberCreate, db: Session = Depends(get_db)
) -> CrewMember:
    _get_production_or_404(db, production_id)
    if db.get(Contact, payload.contact_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    member = CrewMember(production_id=production_id, **payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/productions/{production_id}/crew-members", response_model=list[CrewMemberRead])
def list_crew_members(production_id: uuid.UUID, db: Session = Depends(get_db)) -> list[CrewMember]:
    _get_production_or_404(db, production_id)
    return list(db.query(CrewMember).filter(CrewMember.production_id == production_id).all())

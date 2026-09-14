"""Call sheet endpoints: create, fetch (with current revision), and publish
a new revision.

The GET endpoint below is deliberately unauthenticated (see the separate
`public_router`) because that's the one the offline-first PWA hits from a
crew member's phone — a call sheet is meant to be shareable by link, not
gated behind the same admin token used for authoring. This is a
skeleton-stage simplification: DESIGN.md flags real per-production
share-link auth as a follow-on, not something to fake here.

Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.auth import Principal, require_api_token, require_principal
from app.authz import DAY_PUBLISH, PRODUCTION_READ, require_on
from app.database import get_db
from app.models.call_sheet import CallSheet, CallSheetRevision
from app.models.production import Production
from app.schemas.call_sheet import CallSheetCreate, CallSheetRead, CallSheetRevisionCreate, CallSheetRevisionRead
from app.schemas.call_sheet import PersonalSheet
from app.services.call_sheets import HeadOfDayNotOnProduction, build_contacts, build_personal, create_call_sheet, publish_revision

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_token)])
public_router = APIRouter()  # no auth — see module docstring


def _audit_label(principal: Principal, body_value: str | None) -> str:
    """Users are recorded by identity; service scripts may name themselves, prefixed so it is never mistaken for a person."""
    if principal.kind == "user":
        return principal.label
    return f"service:{body_value or 'unknown'}"


def _get_call_sheet_or_404(db: Session, call_sheet_id: uuid.UUID) -> CallSheet:
    call_sheet = (
        db.query(CallSheet)
        .options(
            selectinload(CallSheet.revisions).selectinload(CallSheetRevision.schedule_items),
            selectinload(CallSheet.revisions).selectinload(CallSheetRevision.cast_calls),
        )
        .filter(CallSheet.id == call_sheet_id)
        .first()
    )
    if call_sheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call sheet not found")
    return call_sheet


@router.post(
    "/productions/{production_id}/call-sheets",
    response_model=CallSheetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_call_sheet_endpoint(
    production_id: uuid.UUID,
    payload: CallSheetCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_principal),
) -> CallSheet:
    require_on(db, principal, production_id, DAY_PUBLISH)
    try:
        call_sheet = create_call_sheet(db, production_id, payload, created_by=_audit_label(principal, payload.initial_revision.created_by))
    except HeadOfDayNotOnProduction as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _read_with_contacts(db, call_sheet.id)


@router.post(
    "/call-sheets/{call_sheet_id}/revisions",
    response_model=CallSheetRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
def publish_revision_endpoint(
    call_sheet_id: uuid.UUID,
    payload: CallSheetRevisionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_principal),
):
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, DAY_PUBLISH)
    try:
        return publish_revision(db, call_sheet, payload, created_by=_audit_label(principal, payload.created_by))
    except HeadOfDayNotOnProduction as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValueError as exc:
        # 26 revisions/day exhausted — a real operational limit, not a bug,
        # so it's a 409 (Conflict) rather than a 500.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/productions/{production_id}/call-sheets", response_model=list[CallSheetRead])
def list_call_sheets(
    production_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)
) -> list[CallSheetRead]:
    """The production's days, oldest first, each with its current revision."""
    require_on(db, principal, production_id, PRODUCTION_READ)
    sheets = (
        db.query(CallSheet)
        .options(selectinload(CallSheet.revisions).selectinload(CallSheetRevision.schedule_items))
        .filter(CallSheet.production_id == production_id)
        .order_by(CallSheet.shoot_date, CallSheet.day_number)
        .all()
    )
    return [CallSheetRead.model_validate(sheet) for sheet in sheets]


def _read_with_contacts(db: Session, call_sheet_id: uuid.UUID) -> CallSheetRead:
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    read = CallSheetRead.model_validate(call_sheet)
    read.contacts = build_contacts(db, call_sheet)
    return read


@router.get("/call-sheets/{call_sheet_id}", response_model=CallSheetRead)
def get_call_sheet(
    call_sheet_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)
) -> CallSheetRead:
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, PRODUCTION_READ)
    return _read_with_contacts(db, call_sheet_id)


@public_router.get("/public/call-sheets/{call_sheet_id}", response_model=CallSheetRead)
def get_call_sheet_public(call_sheet_id: uuid.UUID, db: Session = Depends(get_db)) -> CallSheetRead:
    """Unauthenticated read, fetched by the offline-first PWA for caching."""
    return _read_with_contacts(db, call_sheet_id)


@public_router.get("/public/call-sheets/{call_sheet_id}/me/{token}", response_model=PersonalSheet)
def get_personal_public(call_sheet_id: uuid.UUID, token: str, db: Session = Depends(get_db)) -> PersonalSheet:
    """Unauthenticated: the personal block for a crew member's link. 404 for an unknown token."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    personal = build_personal(db, call_sheet, token)
    if personal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This personal link does not belong to a crew member of this production")
    return personal

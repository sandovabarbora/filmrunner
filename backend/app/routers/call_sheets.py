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
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.auth import Principal, require_api_token, require_principal
from app.authz import DAY_PUBLISH, PRODUCTION_READ, require_on
from app.database import get_db
from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus
from app.models.production import Production
from app.schemas.call_sheet import CallSheetCreate, CallSheetRead, CallSheetRevisionCreate, CallSheetRevisionRead
from app.schemas.call_sheet import Actuals, CrewNextDay, PersonalSheet, RevisionSummary, SeenReport
from app.schemas.push import DeliveryFailureRead, NotificationSummaryRead
from app.services.call_sheets import CastCallNotOnProduction, CrewCallNotOnProduction, HeadOfDayNotOnProduction, build_cast_calls, build_contacts, build_personal, build_personal_calls, build_opened_summary, build_seen_report, build_sheet_locations, create_call_sheet, next_day_for_token, previous_revision, publish_revision, record_seen, revision_changes
from app.services.notifications import NotificationSummary, notify_day_cancelled, notify_subscribers

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_token)])
public_router = APIRouter()  # no auth — see module docstring


def _audit_label(principal: Principal, body_value: str | None) -> str:
    """Users are recorded by identity; service scripts may name themselves, prefixed so it is never mistaken for a person."""
    if principal.kind == "user":
        return principal.label
    return f"service:{body_value or 'unknown'}"


def _summary_read(summary: NotificationSummary) -> NotificationSummaryRead:
    return NotificationSummaryRead(
        attempted=summary.attempted,
        delivered=summary.delivered,
        failed=[DeliveryFailureRead(crew_member_name=f.crew_member_name, reason=f.reason) for f in summary.failed],
    )


def _get_call_sheet_or_404(db: Session, call_sheet_id: uuid.UUID) -> CallSheet:
    call_sheet = (
        db.query(CallSheet)
        .options(
            selectinload(CallSheet.revisions).selectinload(CallSheetRevision.schedule_items),
            selectinload(CallSheet.revisions).selectinload(CallSheetRevision.cast_calls),
            selectinload(CallSheet.revisions).selectinload(CallSheetRevision.crew_calls),
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
    except (HeadOfDayNotOnProduction, CrewCallNotOnProduction, CastCallNotOnProduction) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    summary = notify_subscribers(db, call_sheet, call_sheet.current_revision) if not payload.draft else NotificationSummary()
    read = _read_with_contacts(db, call_sheet.id)
    if read.current_revision is not None:
        read.current_revision.notifications = _summary_read(summary)
    return read


@router.put("/call-sheets/{call_sheet_id}/actuals", response_model=CallSheetRead)
def set_actuals(call_sheet_id: uuid.UUID, payload: Actuals, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> CallSheetRead:
    """FR-65: what actually happened. Only on a published day: a draft has not happened and a cancelled one did not."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, DAY_PUBLISH)
    if call_sheet.status != CallSheetStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Actual times need a published day; this one is {call_sheet.status.value}")

    def clean(v: str | None) -> str | None:
        return (v.strip() or None) if isinstance(v, str) else None

    call_sheet.actual_first_shot = clean(payload.first_shot)
    call_sheet.actual_lunch_out = clean(payload.lunch_out)
    call_sheet.actual_lunch_in = clean(payload.lunch_in)
    call_sheet.actual_wrap = clean(payload.wrap)
    call_sheet.actual_note = clean(payload.note)
    db.commit()
    return _read_with_contacts(db, call_sheet_id)


@router.delete("/call-sheets/{call_sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft_call_sheet(call_sheet_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> None:
    """FR-56: only a day nobody has seen (status draft) can be deleted; a published day is cancelled instead."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, DAY_PUBLISH)
    if call_sheet.status != CallSheetStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an unpublished draft can be deleted; cancel a published day instead")
    for rev in list(call_sheet.revisions):
        for child in list(rev.schedule_items) + list(rev.cast_calls) + list(rev.crew_calls):
            db.delete(child)
        db.delete(rev)
    db.delete(call_sheet)
    db.commit()


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
        revision = publish_revision(db, call_sheet, payload, created_by=_audit_label(principal, payload.created_by))
    except (HeadOfDayNotOnProduction, CrewCallNotOnProduction, CastCallNotOnProduction) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValueError as exc:
        # 26 revisions/day exhausted — a real operational limit, not a bug,
        # so it's a 409 (Conflict) rather than a 500.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    summary = notify_subscribers(db, call_sheet, revision)
    read = CallSheetRevisionRead.model_validate(revision)
    read.notifications = _summary_read(summary)
    return read


@router.post("/call-sheets/{call_sheet_id}/cancel", response_model=CallSheetRead)
def cancel_call_sheet(call_sheet_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> CallSheetRead:
    """FR-34: the day is off. The sheet stays readable with a CANCELLED banner and every subscriber is told; nothing is deleted."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, DAY_PUBLISH)
    if call_sheet.status != CallSheetStatus.CANCELLED:
        call_sheet.status = CallSheetStatus.CANCELLED
        db.commit()
        logger.info("Call sheet %s (day %d) cancelled by %s", call_sheet.id, call_sheet.day_number, principal.label)
    summary = notify_day_cancelled(db, call_sheet)
    read = _read_with_contacts(db, call_sheet_id)
    if read.current_revision is not None:
        read.current_revision.notifications = _summary_read(summary)
    return read


@router.post("/call-sheets/{call_sheet_id}/restore", response_model=CallSheetRead)
def restore_call_sheet(call_sheet_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> CallSheetRead:
    """Undo a cancellation; the AD then publishes a revision so the crew gets told the day is back on."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, DAY_PUBLISH)
    if call_sheet.status == CallSheetStatus.CANCELLED:
        call_sheet.status = CallSheetStatus.PUBLISHED
        db.commit()
        logger.info("Call sheet %s (day %d) restored by %s", call_sheet.id, call_sheet.day_number, principal.label)
    return _read_with_contacts(db, call_sheet_id)


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
    reads = []
    for sheet in sheets:
        read = CallSheetRead.model_validate(sheet)
        read.opened = build_opened_summary(db, sheet)
        read.actuals = _actuals_of(sheet)
        if read.current_revision is not None:
            # The list shows the call, the first location and a count; the scenes belong to the day screen.
            # FR-52: with 30 days of 50 scenes this was 520 KB and 2.8 s on a phone — now ~15 KB.
            read.current_revision.schedule_items = []
            read.current_revision.cast_calls = []
            read.current_revision.crew_calls = []
        reads.append(read)
    return reads


def _actuals_of(call_sheet: CallSheet) -> Actuals:
    return Actuals(first_shot=call_sheet.actual_first_shot, lunch_out=call_sheet.actual_lunch_out, lunch_in=call_sheet.actual_lunch_in,
                   wrap=call_sheet.actual_wrap, note=call_sheet.actual_note)


def _read_with_contacts(db: Session, call_sheet_id: uuid.UUID, *, public: bool = False) -> CallSheetRead:
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    read = CallSheetRead.model_validate(call_sheet)
    if not public:
        read.actuals = _actuals_of(call_sheet)
    read.contacts = build_contacts(db, call_sheet)
    read.personal_calls = build_personal_calls(db, call_sheet)
    read.cast_calls = build_cast_calls(db, call_sheet)
    read.locations = build_sheet_locations(db, call_sheet)
    prev = previous_revision(call_sheet)
    if prev is not None and call_sheet.current_revision is not None:
        read.previous_revision = RevisionSummary(revision_letter=prev.revision_letter, created_at=prev.created_at)
        read.changes = revision_changes(prev, call_sheet.current_revision)
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
    """Unauthenticated read, fetched by the offline-first PWA for caching. A draft day (FR-56) does not exist for the crew."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    if call_sheet.status == CallSheetStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call sheet not found")
    return _read_with_contacts(db, call_sheet_id, public=True)


@public_router.get("/public/call-sheets/{call_sheet_id}/me/{token}", response_model=PersonalSheet)
def get_personal_public(call_sheet_id: uuid.UUID, token: str, db: Session = Depends(get_db)) -> PersonalSheet:
    """Unauthenticated: the personal block for a crew member's link. 404 for an unknown token."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    personal = build_personal(db, call_sheet, token)
    if personal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This personal link does not belong to a crew member of this production")
    return personal


@public_router.get("/public/crew/{token}/next", response_model=CrewNextDay)
def get_next_day_public(token: str, db: Session = Depends(get_db)) -> CrewNextDay:
    """Unauthenticated: where a crew member's stable link opens (FR-32). "Today" is Prague's today, where the pilot crews are."""
    today = datetime.now(ZoneInfo("Europe/Prague")).date()
    result = next_day_for_token(db, token, today)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This personal link does not belong to a crew member")
    return result


@public_router.post("/public/call-sheets/{call_sheet_id}/seen/{token}", status_code=status.HTTP_204_NO_CONTENT)
def mark_seen_public(call_sheet_id: uuid.UUID, token: str, db: Session = Depends(get_db)) -> None:
    """Unauthenticated: the personal link loaded this sheet live (FR-36). Idempotent; 404 for an unknown token."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    if not record_seen(db, call_sheet, token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This personal link does not belong to a crew member of this production")


@router.get("/call-sheets/{call_sheet_id}/seen", response_model=SeenReport)
def get_seen_report(call_sheet_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(require_principal)) -> SeenReport:
    """Who has opened the current revision (FR-36); the AD's answer to "did everyone get REV B?"."""
    call_sheet = _get_call_sheet_or_404(db, call_sheet_id)
    require_on(db, principal, call_sheet.production_id, PRODUCTION_READ)
    report = build_seen_report(db, call_sheet)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No revision published yet")
    return report

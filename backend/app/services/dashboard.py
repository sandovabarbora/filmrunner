import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session, selectinload

from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus
from app.models.production import Production
from app.schemas.dashboard import Dashboard, DashboardItem, OnTrackProduction
from app.services.call_sheets import build_seen_report

# Today, tomorrow and the day after: past that, nothing needs chasing yet.
WATCH_DAYS = 2
_KIND_ORDER = {"unconfirmed": 0, "no_crew": 1, "unpublished": 2}


def _waiting_item(production: Production, sheet: CallSheet, today: date, db: Session) -> DashboardItem | None:
    report = build_seen_report(db, sheet)
    if report is None:
        return None
    everyone = report.seen + report.not_seen
    if not everyone:
        # Nobody is told about this day. "All confirmed" would be true of the empty list, and false comfort.
        return DashboardItem(
            kind="no_crew", production_id=production.id, production_name=production.name, call_sheet_id=sheet.id,
            shoot_date=sheet.shoot_date, day_number=sheet.day_number, revision_letter=report.revision_letter,
            crew_call=sheet.current_revision.general_crew_call,
        )
    confirmed = sum(1 for e in everyone if e.confirmed_at is not None)
    if confirmed == len(everyone):
        return None
    # A first revision two days out is routine, not a problem: people confirm it as the day comes close.
    if report.revision_letter == "A" and sheet.shoot_date > today + timedelta(days=1):
        return None
    return DashboardItem(
        kind="unconfirmed", production_id=production.id, production_name=production.name, call_sheet_id=sheet.id,
        shoot_date=sheet.shoot_date, day_number=sheet.day_number, revision_letter=report.revision_letter,
        crew_call=sheet.current_revision.general_crew_call, total=len(everyone), confirmed=confirmed, not_opened=len(report.not_seen),
    )



def build_dashboard(db: Session, productions: list[Production], today: date) -> Dashboard:
    if not productions:
        return Dashboard(items=[], on_track=[])
    by_production: dict[uuid.UUID, list[CallSheet]] = {p.id: [] for p in productions}
    upcoming = (
        db.query(CallSheet)
        .options(selectinload(CallSheet.revisions).selectinload(CallSheetRevision.cast_calls))
        .filter(CallSheet.production_id.in_(by_production), CallSheet.shoot_date >= today, CallSheet.status != CallSheetStatus.CANCELLED)
        .order_by(CallSheet.shoot_date, CallSheet.day_number)
        .all()
    )
    for sheet in upcoming:
        by_production[sheet.production_id].append(sheet)

    items: list[DashboardItem] = []
    on_track: list[OnTrackProduction] = []
    last_watched = today + timedelta(days=WATCH_DAYS)
    for production in productions:
        sheets = by_production[production.id]
        found: list[DashboardItem] = []
        for sheet in (s for s in sheets if s.shoot_date <= last_watched):
            if sheet.status == CallSheetStatus.DRAFT:
                found.append(DashboardItem(
                    kind="unpublished", production_id=production.id, production_name=production.name, call_sheet_id=sheet.id,
                    shoot_date=sheet.shoot_date, day_number=sheet.day_number,
                ))
            elif (item := _waiting_item(production, sheet, today, db)) is not None:
                found.append(item)
        items.extend(found)
        if not found:
            next_day = sheets[0] if sheets else None
            on_track.append(OnTrackProduction(
                production_id=production.id, production_name=production.name,
                next_call_sheet_id=next_day.id if next_day else None, next_shoot_date=next_day.shoot_date if next_day else None,
                crew_call=next_day.current_revision.general_crew_call if next_day and next_day.current_revision else None,
            ))
    # Whatever happens soonest comes first; on the same day, people who do not know yet outrank a day with nobody on it, then a sheet not yet out.
    items.sort(key=lambda i: (i.shoot_date, _KIND_ORDER[i.kind], i.production_name.lower()))
    on_track.sort(key=lambda p: (p.next_shoot_date is None, p.next_shoot_date or date.max, p.production_name.lower()))
    return Dashboard(items=items, on_track=on_track)

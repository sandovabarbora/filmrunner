"""How many stored sunrise and sunset values carry the FR-222 rounding bug.

Until FR-222 a minute that rounded up to 60 became :00 without carrying the
hour, so 07:00 was stored as 06:00. Revisions are immutable and are never
rewritten, so those values stay until the AD publishes a corrected revision.

A value counts as affected when it equals what the old arithmetic gives for the
day's first located scene and differs from the correct time. A location moved on
the map after publishing is missed; a typed value matching by chance is counted.

Read-only: the transaction is set READ ONLY, so the database refuses any write.

Usage:
    cd backend && python -m scripts.sun_rollover_report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.clock import prague_today
from app.database import SessionLocal
from app.models.call_sheet import CallSheet, CallSheetRevision
from app.models.production import Location
from app.services.astronomy import _sun_time_utc_hours, sunrise_sunset


def _old_hhmm(hours: float, on_date: date) -> str:
    """The arithmetic FR-222 replaced, kept here only to recognise what it wrote."""
    hour = int(hours) % 24
    minute = int(round((hours - int(hours)) * 60)) % 60
    instant = datetime(on_date.year, on_date.month, on_date.day, hour, minute, tzinfo=timezone.utc)
    return instant.astimezone(ZoneInfo("Europe/Prague")).strftime("%H:%M")


def is_affected(revision: CallSheetRevision, location: Location, on_date: date) -> bool:
    correct = sunrise_sunset(location.geo_lat, location.geo_lng, on_date)
    if correct[0] is None:
        return False
    for stored, good, is_sunrise in ((revision.sunrise, correct[0], True), (revision.sunset, correct[1], False)):
        hours = _sun_time_utc_hours(is_sunrise, location.geo_lat, location.geo_lng, on_date)
        if stored != good and stored == _old_hhmm(hours, on_date):
            return True
    return False


@dataclass
class Report:
    revisions_checked: int = 0
    revisions_affected: int = 0
    days_showing_wrong_now: list[tuple[str, date, int, str]] = field(default_factory=list)
    upcoming_days_showing_wrong_now: int = 0


def build_report(db: Session, today: date) -> Report:
    report = Report()
    sheets = db.query(CallSheet).options(selectinload(CallSheet.revisions).selectinload(CallSheetRevision.schedule_items)).all()
    for sheet in sheets:
        for revision in sheet.revisions:
            on_date = revision.shoot_date or sheet.shoot_date
            located = sorted((i for i in revision.schedule_items if i.location_id is not None), key=lambda i: i.order_index)
            location = db.get(Location, located[0].location_id) if located else None
            if location is None or location.geo_lat is None or location.geo_lng is None:
                continue
            report.revisions_checked += 1
            if not is_affected(revision, location, on_date):
                continue
            report.revisions_affected += 1
            if revision.is_current:
                report.days_showing_wrong_now.append((str(sheet.id), sheet.shoot_date, sheet.day_number, revision.revision_letter))
                if sheet.shoot_date >= today:
                    report.upcoming_days_showing_wrong_now += 1
    return report


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        report = build_report(db, prague_today())
    finally:
        db.rollback()
        db.close()
    print(f"Revisions with a located first scene checked: {report.revisions_checked}")
    print(f"Revisions holding a value the bug wrote: {report.revisions_affected}")
    print(f"Days whose current revision still shows one: {len(report.days_showing_wrong_now)}")
    print(f"... of those, today or later: {report.upcoming_days_showing_wrong_now}")
    for sheet_id, shoot_date, day_number, letter in sorted(report.days_showing_wrong_now, key=lambda row: row[1]):
        print(f"  {shoot_date}  Day {day_number}  REV {letter}  {sheet_id}")


if __name__ == "__main__":
    main()

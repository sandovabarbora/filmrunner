"""FR-222: the founder's read-only count of stored sun times the rounding bug wrote."""

from datetime import date

from scripts.sun_rollover_report import build_report

from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus, DayNight, IntExt, ScheduleItem
from app.models.production import Location, Production

BUGGY_DAY = date(2026, 11, 6)


def _revision(db, sheet: CallSheet, location: Location, letter: str, sunrise: str, *, current: bool) -> None:
    revision = CallSheetRevision(call_sheet_id=sheet.id, revision_letter=letter, is_current=current, sunrise=sunrise, sunset="16:31", shoot_date=sheet.shoot_date)
    db.add(revision)
    db.flush()
    db.add(ScheduleItem(revision_id=revision.id, order_index=1, scene_number="1", int_ext=IntExt.EXT, day_night=DayNight.DAY,
                        set_description="Set", location_id=location.id, page_count_eighths=8))


def test_counts_only_the_values_the_bug_wrote_and_says_which_days_still_show_one(db_session) -> None:
    production = Production(name="Sun")
    db_session.add(production)
    db_session.flush()
    location = Location(production_id=production.id, name="Praha", geo_lat=50.0755, geo_lng=14.4378)
    db_session.add(location)
    fixed = CallSheet(production_id=production.id, shoot_date=BUGGY_DAY, day_number=1, day_count=2, status=CallSheetStatus.PUBLISHED)
    wrong = CallSheet(production_id=production.id, shoot_date=BUGGY_DAY, day_number=2, day_count=2, status=CallSheetStatus.PUBLISHED)
    db_session.add_all([fixed, wrong])
    db_session.flush()
    _revision(db_session, fixed, location, "A", "06:00", current=False)
    _revision(db_session, fixed, location, "B", "07:00", current=True)
    _revision(db_session, wrong, location, "A", "06:00", current=True)
    db_session.commit()

    report = build_report(db_session, date(2026, 11, 7))

    assert report.revisions_affected >= 2
    days = {row[0] for row in report.days_showing_wrong_now}
    assert str(wrong.id) in days and str(fixed.id) not in days
    assert build_report(db_session, BUGGY_DAY).upcoming_days_showing_wrong_now >= 1

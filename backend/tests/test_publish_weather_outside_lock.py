"""FR-223: a slow or failing weather service cannot hold a publish.

Real commits and a second real connection, like test_publish_idempotency.py: only another connection can tell
whether the revision is already visible and the lock already free while the weather call is in flight.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus
from app.models.production import Location, Production
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate, ScheduleItemCreate
from app.services import call_sheets as service
from app.services.replan import move_scene, reschedule_day


def _scene(location_id, number="1", order=1) -> ScheduleItemCreate:
    return ScheduleItemCreate(order_index=order, scene_number=number, int_ext="EXT", day_night="DAY", set_description="Riverbank",
                              page_count_eighths=8, location_id=location_id)


def _create(db, production_id, location_id, day, draft=False) -> CallSheet:
    return service.create_call_sheet(db, production_id, CallSheetCreate(
        shoot_date=date.today() + timedelta(days=day), day_number=day, day_count=3, draft=draft,
        initial_revision=CallSheetRevisionCreate(general_crew_call="05:00", weather_forecast="typed by the AD", schedule_items=[_scene(location_id)]),
    ))


@pytest.fixture()
def world():
    db = SessionLocal()
    production = Production(name=f"FR-223 weather {uuid.uuid4()}")
    db.add(production)
    db.flush()
    location = Location(production_id=production.id, name="Riverbank", address="Troja", geo_lat=50.1, geo_lng=14.4)
    db.add(location)
    db.flush()
    production_id, location_id = production.id, location.id
    db.commit()
    try:
        yield db, production_id, location_id
    finally:
        db.rollback()
        db.close()
        cleanup = SessionLocal()
        for sheet in cleanup.query(CallSheet).filter(CallSheet.production_id == production_id):
            for revision in list(sheet.revisions):
                for child in list(revision.schedule_items) + list(revision.cast_calls) + list(revision.crew_calls):
                    cleanup.delete(child)
                cleanup.flush()
                cleanup.delete(revision)
            cleanup.flush()
            cleanup.delete(sheet)
        cleanup.flush()
        cleanup.query(Location).filter(Location.production_id == production_id).delete()
        cleanup.query(Production).filter(Production.id == production_id).delete()
        cleanup.commit()
        cleanup.close()


def _probe(sheet_id) -> tuple[bool, str]:
    """From another connection, what the crew and a second publisher would meet right now."""
    with SessionLocal() as other:
        lock_free = other.execute(text("SELECT pg_try_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": str(sheet_id)}).scalar()
        letter = other.query(CallSheetRevision.revision_letter).filter_by(call_sheet_id=sheet_id, is_current=True).scalar()
    return lock_free, letter


def test_revision_is_visible_and_the_lock_free_while_weather_is_in_flight(world, monkeypatch):
    db, production_id, location_id = world
    sheet = _create(db, production_id, location_id, day=1)
    sheet_id = sheet.id
    seen = []

    def slow_weather(lat, lng, on_date):
        seen.append(_probe(sheet_id))
        return "9-18°C, slight rain"

    monkeypatch.setattr(service.weather, "weather_suggestion", slow_weather)
    revision, is_new = service.publish_revision(db, sheet, CallSheetRevisionCreate(general_crew_call="05:30", schedule_items=[_scene(location_id)]))
    assert is_new
    assert seen == [(True, "B")]
    assert revision.weather_forecast == "9-18°C, slight rain"


def test_a_failing_weather_call_leaves_the_publish_standing(world, monkeypatch):
    db, production_id, location_id = world
    sheet = _create(db, production_id, location_id, day=1)

    def fails(lat, lng, on_date):
        raise RuntimeError("provider exploded in an unexpected way")

    monkeypatch.setattr(service.weather, "weather_suggestion", fails)
    revision, is_new = service.publish_revision(db, sheet, CallSheetRevisionCreate(general_crew_call="05:30", schedule_items=[_scene(location_id)]))
    assert is_new and revision.revision_letter == "B" and revision.weather_forecast is None
    assert _probe(sheet.id) == (True, "B")


def test_a_late_forecast_does_not_overwrite_a_value_written_meanwhile(world, monkeypatch):
    db, production_id, location_id = world
    sheet = _create(db, production_id, location_id, day=1)
    sheet_id = sheet.id

    def weather_while_someone_writes(lat, lng, on_date):
        with SessionLocal() as other:
            other.execute(text("UPDATE call_sheet_revisions SET weather_forecast = 'written meanwhile' WHERE call_sheet_id = :id AND is_current"), {"id": sheet_id})
            other.commit()
        return "too late"

    monkeypatch.setattr(service.weather, "weather_suggestion", weather_while_someone_writes)
    revision, _ = service.publish_revision(db, sheet, CallSheetRevisionCreate(general_crew_call="05:30", schedule_items=[_scene(location_id)]))
    assert revision.weather_forecast == "written meanwhile"


def test_a_superseded_revision_is_not_changed_by_its_late_forecast(world, monkeypatch):
    db, production_id, location_id = world
    sheet = _create(db, production_id, location_id, day=1)
    sheet_id = sheet.id

    def weather_while_another_publish_lands(lat, lng, on_date):
        with SessionLocal() as other:
            service.publish_revision(other, other.get(CallSheet, sheet_id), CallSheetRevisionCreate(
                general_crew_call="06:00", weather_forecast="newer revision", schedule_items=[_scene(location_id)]))
        return "late for B"

    monkeypatch.setattr(service.weather, "weather_suggestion", weather_while_another_publish_lands)
    revision, _ = service.publish_revision(db, sheet, CallSheetRevisionCreate(general_crew_call="05:30", schedule_items=[_scene(location_id)]))
    assert revision.revision_letter == "B" and revision.weather_forecast is None
    with SessionLocal() as other:
        current = other.query(CallSheetRevision).filter_by(call_sheet_id=sheet_id, is_current=True).one()
        assert (current.revision_letter, current.weather_forecast) == ("C", "newer revision")


@pytest.mark.parametrize("provider_says,expected", [
    ("typed by the AD", []),
    ("9-18°C, slight rain", [("typed by the AD", "9-18°C, slight rain")]),
])
def test_the_crew_diff_after_the_fill_compares_the_real_forecast(world, monkeypatch, provider_says, expected):
    db, production_id, location_id = world
    sheet = _create(db, production_id, location_id, day=1)
    monkeypatch.setattr(service.weather, "weather_suggestion", lambda lat, lng, on_date: provider_says)
    service.publish_revision(db, sheet, CallSheetRevisionCreate(general_crew_call="05:00", schedule_items=[_scene(location_id)]))
    with SessionLocal() as crew_view:
        by_letter = {r.revision_letter: r for r in crew_view.query(CallSheetRevision).filter_by(call_sheet_id=sheet.id)}
        changes = service.revision_changes(by_letter["A"], by_letter["B"])
    assert [(c.before, c.after) for c in changes if c.field == "weather"] == expected


def test_a_new_draft_day_is_never_visible_as_published_during_the_weather_call(world, monkeypatch):
    db, production_id, location_id = world
    statuses = []

    def weather(lat, lng, on_date):
        with SessionLocal() as other:
            statuses.extend(row[0] for row in other.query(CallSheet.status).filter(CallSheet.production_id == production_id))
        return "9-18°C"

    monkeypatch.setattr(service.weather, "weather_suggestion", weather)
    sheet = service.create_call_sheet(db, production_id, CallSheetCreate(
        shoot_date=date.today() + timedelta(days=1), day_number=1, day_count=3, draft=True,
        initial_revision=CallSheetRevisionCreate(general_crew_call="05:00", schedule_items=[_scene(location_id)]),
    ))
    assert statuses == [CallSheetStatus.DRAFT]
    assert sheet.current_revision.weather_forecast == "9-18°C"


def test_moving_a_scene_holds_no_lock_during_weather(world, monkeypatch):
    db, production_id, location_id = world
    other_location = Location(production_id=production_id, name="Hill", address="Petrin", geo_lat=50.0, geo_lng=14.3)
    db.add(other_location)
    db.flush()
    source = service.create_call_sheet(db, production_id, CallSheetCreate(
        shoot_date=date.today() + timedelta(days=1), day_number=1, day_count=3,
        initial_revision=CallSheetRevisionCreate(general_crew_call="05:00", weather_forecast="typed",
                                                 schedule_items=[_scene(location_id), _scene(other_location.id, number="3", order=2)]),
    ))
    target = service.create_call_sheet(db, production_id, CallSheetCreate(
        shoot_date=date.today() + timedelta(days=2), day_number=2, day_count=3,
        initial_revision=CallSheetRevisionCreate(general_crew_call="05:00", weather_forecast="typed", schedule_items=[_scene(other_location.id, number="2")]),
    ))
    target_id, source_id = target.id, source.id
    seen = []

    def weather(lat, lng, on_date):
        seen.append((_probe(source_id), _probe(target_id)))
        return "9-18°C"

    monkeypatch.setattr(service.weather, "weather_suggestion", weather)
    move_scene(db, source, target, "1", 0, "A", "A", "tester")
    assert seen, "the source day starts somewhere else now, so its forecast must be recomputed"
    assert all(probe == ((True, "B"), (True, "B")) for probe in seen)


def test_rescheduling_a_day_holds_no_lock_during_weather(world, monkeypatch):
    db, production_id, location_id = world
    sheet = _create(db, production_id, location_id, day=1)
    sheet_id = sheet.id
    seen = []

    def weather(lat, lng, on_date):
        seen.append(_probe(sheet_id))
        return "9-18°C"

    monkeypatch.setattr(service.weather, "weather_suggestion", weather)
    published = reschedule_day(db, sheet, date.today() + timedelta(days=3), "A", "tester")
    assert seen == [(True, "B")]
    assert published[0][1].weather_forecast == "9-18°C"

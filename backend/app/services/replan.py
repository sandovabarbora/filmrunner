"""FR-203: changing the plan across days, as one action.

Each operation publishes the next revision on every day it touches inside one
transaction: the crew never sees a scene on neither day or on both. The caller
names the revision it was looking at, so a change made from a stale screen is
refused instead of overwriting one published in the meantime.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus, SceneMove
from app.schemas.call_sheet import CallSheetRevisionCreate, CastCallEntryCreate, CrewCallEntryCreate, ScheduleItemCreate
from app.services.call_sheets import fill_weather_after_commit, publish_revision


class ReplanConflict(ValueError):
    """The change cannot be made as asked; the message tells the AD why."""


def _payload(revision: CallSheetRevision, items: list[ScheduleItemCreate] | None = None, *, new_date: bool = False) -> CallSheetRevisionCreate:
    """The revision as a new one, optionally with other scenes. `new_date` recomputes sun and weather, which depend on the date and the first location."""
    return CallSheetRevisionCreate(
        general_crew_call=revision.general_crew_call,
        shooting_call=revision.shooting_call,
        sunrise=None if new_date else revision.sunrise,
        sunset=None if new_date else revision.sunset,
        weather_forecast=None if new_date else revision.weather_forecast,
        safety_notes=revision.safety_notes,
        head_of_day_crew_member_id=revision.head_of_day_crew_member_id,
        schedule_items=items if items is not None else _items(revision),
        cast_calls=[CastCallEntryCreate(cast_member_id=e.cast_member_id, status_code=e.status_code, pickup_time=e.pickup_time, call_time=e.call_time,
                                        makeup_hair_time=e.makeup_hair_time, on_set_time=e.on_set_time) for e in revision.cast_calls],
        crew_calls=[CrewCallEntryCreate(crew_member_id=e.crew_member_id, call_time=e.call_time, pickup_time=e.pickup_time, note=e.note) for e in revision.crew_calls],
    )


def _items(revision: CallSheetRevision) -> list[ScheduleItemCreate]:
    return [
        ScheduleItemCreate(order_index=i.order_index, scene_number=i.scene_number, int_ext=i.int_ext, day_night=i.day_night,
                           set_description=i.set_description, location_id=i.location_id, page_count_eighths=i.page_count_eighths)
        for i in sorted(revision.schedule_items, key=lambda i: i.order_index)
    ]


def _renumbered(items: list[ScheduleItemCreate]) -> list[ScheduleItemCreate]:
    return [item.model_copy(update={"order_index": i}) for i, item in enumerate(items, start=1)]


def _current(sheet: CallSheet, expected_letter: str) -> CallSheetRevision:
    revision = sheet.current_revision
    if sheet.status == CallSheetStatus.CANCELLED:
        raise ReplanConflict(f"Day {sheet.day_number} is cancelled; restore it first")
    if revision is None:
        raise ReplanConflict(f"Day {sheet.day_number} has nothing published yet")
    if revision.revision_letter != expected_letter:
        raise ReplanConflict(f"Day {sheet.day_number} is now at REV {revision.revision_letter}, not {expected_letter}; reload and try again")
    return revision


def _publish(db: Session, sheet: CallSheet, payload: CallSheetRevisionCreate, created_by: str | None) -> CallSheetRevision:
    """Publish without committing. A planned day stays planned: replanning around it must not reveal it to the crew."""
    was_draft = sheet.status == CallSheetStatus.DRAFT
    revision, is_new = publish_revision(db, sheet, payload, created_by=created_by, commit=False)
    if not is_new:
        raise ReplanConflict(f"Day {sheet.day_number} was published by someone else just now; reload and try again")
    if was_draft:
        sheet.status = CallSheetStatus.DRAFT
    return revision


def _ordered(*sheets: CallSheet) -> list[CallSheet]:
    return sorted(sheets, key=lambda s: str(s.id))


def _lock(db: Session, *sheets: CallSheet) -> None:
    """Take every day's publish lock before looking at it, in a stable order so two changes between the same days cannot
    deadlock. Without this the letter check could pass, then a publish slip in, and the scene end up on both days. The
    same key publish_revision uses, and advisory locks are reentrant, so its own attempt then succeeds at once."""
    for sheet in _ordered(*sheets):
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": str(sheet.id)})
        db.expire(sheet)


def _fill_weather(db: Session, *revisions: CallSheetRevision) -> None:
    for revision in revisions:
        fill_weather_after_commit(db, revision)


def _first_location(items: list[ScheduleItemCreate]):
    return next((i.location_id for i in items if i.location_id is not None), None)


def move_scene(
    db: Session, source: CallSheet, target: CallSheet, scene_number: str, occurrence: int,
    expected_letter: str, expected_target_letter: str, created_by: str | None,
) -> list[tuple[CallSheet, CallSheetRevision]]:
    """Move one scene to the end of another day's schedule. Returns the revisions the crew must be told about."""
    if source.id == target.id:
        raise ReplanConflict("The scene is already on this day")
    if source.production_id != target.production_id:
        raise ReplanConflict("That day belongs to another production")
    _lock(db, source, target)
    source_rev, target_rev = _current(source, expected_letter), _current(target, expected_target_letter)
    items = _items(source_rev)
    matching = [i for i, item in enumerate(items) if item.scene_number == scene_number]
    if occurrence >= len(matching):
        raise ReplanConflict(f"Scene {scene_number} is not on Day {source.day_number}")
    target_items = _items(target_rev)
    was_first = {source.id: _first_location(items), target.id: _first_location(target_items)}
    moved = items.pop(matching[occurrence])
    target_items.append(moved)
    # Sun and weather come from the first location: when a day starts somewhere else they are stale.
    payloads = {
        source.id: _payload(source_rev, _renumbered(items), new_date=_first_location(items) != was_first[source.id]),
        target.id: _payload(target_rev, _renumbered(target_items), new_date=_first_location(target_items) != was_first[target.id]),
    }
    published = {sheet.id: _publish(db, sheet, payloads[sheet.id], created_by) for sheet in _ordered(source, target)}
    db.add(SceneMove(scene_number=scene_number, from_revision_id=published[source.id].id, to_revision_id=published[target.id].id))
    db.commit()
    _fill_weather(db, *published.values())
    return [(sheet, published[sheet.id]) for sheet in (source, target) if sheet.status != CallSheetStatus.DRAFT]


def _unit_day_on(db: Session, sheet: CallSheet, shoot_date: date) -> CallSheet | None:
    return (
        db.query(CallSheet)
        .filter(CallSheet.production_id == sheet.production_id, CallSheet.unit_name == sheet.unit_name, CallSheet.shoot_date == shoot_date,
                CallSheet.id != sheet.id, CallSheet.status != CallSheetStatus.CANCELLED)
        .first()
    )


def reschedule_day(db: Session, sheet: CallSheet, shoot_date: date, expected_letter: str, created_by: str | None) -> list[tuple[CallSheet, CallSheetRevision]]:
    """Move a whole shoot day to another date."""
    _lock(db, sheet)
    revision = _current(sheet, expected_letter)
    if sheet.shoot_date == shoot_date:
        raise ReplanConflict(f"Day {sheet.day_number} is already on {shoot_date.isoformat()}")
    clash = _unit_day_on(db, sheet, shoot_date)
    if clash is not None:
        raise ReplanConflict(f"Day {clash.day_number} is already on {shoot_date.isoformat()}; swap the two days instead")
    sheet.shoot_date = shoot_date
    published = _publish(db, sheet, _payload(revision, new_date=True), created_by)
    db.commit()
    _fill_weather(db, published)
    return [] if sheet.status == CallSheetStatus.DRAFT else [(sheet, published)]


def swap_days(db: Session, a: CallSheet, b: CallSheet, expected_letter: str, expected_other_letter: str, created_by: str | None) -> list[tuple[CallSheet, CallSheetRevision]]:
    """The two days trade places: each takes the other's date and day number, and keeps its own scenes and calls."""
    if a.id == b.id:
        raise ReplanConflict("Pick another day to swap with")
    if a.production_id != b.production_id:
        raise ReplanConflict("That day belongs to another production")
    _lock(db, a, b)
    rev_a, rev_b = _current(a, expected_letter), _current(b, expected_other_letter)
    payloads = {a.id: _payload(rev_a, new_date=True), b.id: _payload(rev_b, new_date=True)}
    a.shoot_date, b.shoot_date = b.shoot_date, a.shoot_date
    a.day_number, b.day_number = b.day_number, a.day_number
    published = {sheet.id: _publish(db, sheet, payloads[sheet.id], created_by) for sheet in _ordered(a, b)}
    db.commit()
    _fill_weather(db, *published.values())
    return [(sheet, published[sheet.id]) for sheet in (a, b) if sheet.status != CallSheetStatus.DRAFT]

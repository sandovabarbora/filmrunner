"""Business logic for publishing call-sheet revisions.

Kept separate from the router (I/O layer) per the "separate business logic
from I/O" standard — this module has no FastAPI imports and is unit-testable
without spinning up the HTTP layer.

Reference: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
"""

import logging
import string
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.production import CastMember, CrewMember, Location
from app.models.push import PushSubscription
from app.models.seen import RevisionView
from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus, CastCallEntry, CrewCallEntry, DistributionChannel, DistributionLog, ScheduleItem
from app.schemas.call_sheet import CallSheetContacts, CastCallEntryCreate, CastCallRow, ContactCard, CrewCallEntryCreate, SheetLocation, CrewDayRef, CrewNextDay, HistoryEntry, PersonalCallRow, PersonalSheet, OpenedSummary, SeenEntry, SeenReport, CallSheetCreate, CallSheetRevisionCreate, RevisionChange, RevisionSummary
from app.schemas.push import DeliveryFailureRead, NotificationSummaryRead
from app.services import weather
from app.services.astronomy import sunrise_sunset

logger = logging.getLogger(__name__)

_REVISION_LETTERS = string.ascii_uppercase  # A, B, C, ... Z (26 revisions/day is already an incident)


def _next_revision_letter(call_sheet: CallSheet) -> str:
    """Return the next revision letter for a call sheet.

    Raises:
        ValueError: if more than 26 revisions are requested in one day —
            at that point something upstream is broken and silently
            wrapping to "AA" would hide it.
    """
    count = len(call_sheet.revisions)
    if count >= len(_REVISION_LETTERS):
        raise ValueError(
            f"Call sheet {call_sheet.id} already has {count} revisions; "
            "refusing to generate a 27th (A-Z exhausted)."
        )
    return _REVISION_LETTERS[count]


def _fill_computed_sunrise_sunset(db: Session, revision: CallSheetRevision, shoot_date, schedule_items) -> None:
    """FR-19/ADR-006: sunrise and sunset are a computed value, not a
    provider guess, so they auto-fill from the day's first scheduled
    location when the AD leaves both fields blank — same as an AD would
    otherwise type them from another app. Never overwrites a value the AD
    did type (checked by the caller: only called when both are None)."""
    ordered = sorted((i for i in schedule_items if i.location_id is not None), key=lambda i: i.order_index)
    if not ordered:
        return
    location = db.get(Location, ordered[0].location_id)
    if location is None or location.geo_lat is None or location.geo_lng is None:
        return
    rise, sset = sunrise_sunset(location.geo_lat, location.geo_lng, shoot_date)
    revision.sunrise = rise
    revision.sunset = sset


def _fill_weather_forecast(db: Session, revision: CallSheetRevision, shoot_date, schedule_items) -> None:
    """FR-39: same idea as the sunrise/sunset auto-fill — a blank weather
    line reads as "not checked", so publish fills it from the day's first
    located scene with the same suggestion text the "Suggest weather"
    button would give. Never overwrites a value the AD typed (checked by
    the caller). `weather_suggestion` already has its own timeout and
    returns None on any failure, so a down provider never fails or delays
    the publish — the field is simply left blank."""
    # Open-Meteo forecasts 16 days ahead and nothing in the past; outside that window the call can only
    # fail (FR-52 found a 400 per publish on a 30-day schedule import), so it is not made.
    horizon = (shoot_date - date.today()).days
    if horizon < 0 or horizon > 16:
        return
    ordered = sorted((i for i in schedule_items if i.location_id is not None), key=lambda i: i.order_index)
    if not ordered:
        return
    location = db.get(Location, ordered[0].location_id)
    if location is None or location.geo_lat is None or location.geo_lng is None:
        return
    suggestion = weather.weather_suggestion(location.geo_lat, location.geo_lng, shoot_date)
    if suggestion is not None:
        revision.weather_forecast = suggestion


def publish_revision(
    db: Session, call_sheet: CallSheet, payload: CallSheetRevisionCreate, created_by: str | None = None
) -> tuple[CallSheetRevision, bool]:
    """Create a new revision on an existing call sheet, marking prior
    revisions as no longer current.

    This is the "hot revision" operation: same-day corrections happen by
    adding a new immutable revision, never by editing an existing one — see
    DESIGN.md for why.

    Returns (revision, is_new). FR-142: a double-tap or a flaky-connection
    retry can send two publish requests for the same call sheet within
    milliseconds of each other. A Postgres transaction-scoped advisory
    lock keyed on the call sheet serializes them; whichever call has to
    wait for the other re-reads the call sheet once it gets the lock, and
    if a revision was actually added while it waited, that call is the
    duplicate half of the double-tap — it returns the revision the other
    call just published, with is_new=False, instead of publishing a
    second one. The caller must not send a second push when is_new is
    False. A normal sequential pair of calls (an AD publishes now, then a
    real correction minutes later) never contends for the lock, so each
    still gets its own distinct revision exactly as before.
    """
    revision_count_before_lock = len(call_sheet.revisions)
    lock_key = str(call_sheet.id)
    acquired_without_waiting = db.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": lock_key}
    ).scalar()
    if not acquired_without_waiting:
        # Someone else is publishing this exact call sheet right now. Wait for
        # them — the lock releases automatically at the end of their
        # transaction — rather than racing the "one current revision" unique
        # index below.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": lock_key})
        db.expire(call_sheet)
        if len(call_sheet.revisions) != revision_count_before_lock:
            duplicate_of = call_sheet.current_revision
            assert duplicate_of is not None  # a revision was just added, so one is current
            return duplicate_of, False
        # They errored out or published nothing (e.g. a validation failure):
        # fall through and publish for real, now holding the lock ourselves.

    head_of_day_id = _validate_head_of_day(db, call_sheet.production_id, payload.head_of_day_crew_member_id)
    previous = call_sheet.current_revision
    if call_sheet.status == CallSheetStatus.DRAFT and previous is not None:
        # A draft day (FR-56) was never seen by anyone: its content is replaced, not revised, so the
        # first thing the crew sees is REV A. Copy-forward below still reads `previous` first.
        replaced = previous
        crew_calls_seed = list(replaced.crew_calls)
        cast_calls_seed = list(replaced.cast_calls)
        previous = None
    else:
        replaced = None
        crew_calls_seed = None
        cast_calls_seed = None
    if payload.crew_calls is None:
        # Copy forward: the AD edits yesterday's personal calls, they never retype them.
        crew_calls = [
            CrewCallEntryCreate(crew_member_id=e.crew_member_id, call_time=e.call_time, pickup_time=e.pickup_time, note=e.note)
            for e in (previous.crew_calls if previous is not None else (crew_calls_seed or []))
            if db.get(CrewMember, e.crew_member_id) is not None
        ]
    else:
        crew_calls = payload.crew_calls
        for entry in crew_calls:
            member = db.get(CrewMember, entry.crew_member_id)
            if member is None or member.production_id != call_sheet.production_id:
                raise CrewCallNotOnProduction("personal calls must name crew members of this production")

    if payload.cast_calls is None:
        cast_calls = [
            CastCallEntryCreate(cast_member_id=e.cast_member_id, status_code=e.status_code, pickup_time=e.pickup_time,
                                call_time=e.call_time, makeup_hair_time=e.makeup_hair_time, on_set_time=e.on_set_time)
            for e in (previous.cast_calls if previous is not None else (cast_calls_seed or []))
            if db.get(CastMember, e.cast_member_id) is not None
        ]
    else:
        cast_calls = payload.cast_calls
        for cast_call in cast_calls:
            actor = db.get(CastMember, cast_call.cast_member_id)
            if actor is None or actor.production_id != call_sheet.production_id:
                raise CastCallNotOnProduction("cast calls must name cast members of this production")

    if replaced is not None:
        for child in list(replaced.schedule_items) + list(replaced.cast_calls) + list(replaced.crew_calls):
            db.delete(child)
        db.delete(replaced)
        db.flush()
        call_sheet.revisions.remove(replaced)
    for existing in call_sheet.revisions:
        existing.is_current = False
    # A published revision means the day is on: this also puts a cancelled day back (FR-34), telling the crew via the revision push.
    call_sheet.status = CallSheetStatus.PUBLISHED

    revision = CallSheetRevision(
        call_sheet_id=call_sheet.id,
        revision_letter=_next_revision_letter(call_sheet),
        is_current=True,
        general_crew_call=payload.general_crew_call,
        shooting_call=payload.shooting_call,
        sunrise=payload.sunrise,
        sunset=payload.sunset,
        weather_forecast=payload.weather_forecast,
        safety_notes=payload.safety_notes,
        # Audit field comes from the authenticated caller, never from the body.
        created_by=created_by if created_by is not None else payload.created_by,
        head_of_day_crew_member_id=head_of_day_id,
    )
    db.add(revision)
    db.flush()  # assign revision.id before building children

    for item in payload.schedule_items:
        db.add(ScheduleItem(revision_id=revision.id, **item.model_dump()))
    for entry in crew_calls:
        db.add(CrewCallEntry(revision_id=revision.id, **entry.model_dump()))
    for cast_call in cast_calls:
        db.add(CastCallEntry(revision_id=revision.id, **cast_call.model_dump()))

    if revision.sunrise is None and revision.sunset is None:
        _fill_computed_sunrise_sunset(db, revision, call_sheet.shoot_date, payload.schedule_items)
    if not revision.weather_forecast:
        _fill_weather_forecast(db, revision, call_sheet.shoot_date, payload.schedule_items)

    db.commit()
    db.refresh(revision)
    logger.info(
        "Published revision %s for call sheet %s (%d schedule items, %d cast calls)",
        revision.revision_letter,
        call_sheet.id,
        len(payload.schedule_items),
        len(cast_calls),
    )
    return revision, True


def create_call_sheet(db: Session, production_id, payload: CallSheetCreate, created_by: str | None = None) -> CallSheet:
    """Create a call sheet together with its initial revision ('A')."""
    call_sheet = CallSheet(
        production_id=production_id,
        shoot_date=payload.shoot_date,
        day_number=payload.day_number,
        day_count=payload.day_count,
        unit_name=payload.unit_name,
    )
    db.add(call_sheet)
    db.flush()

    publish_revision(db, call_sheet, payload.initial_revision, created_by=created_by)
    if payload.draft:
        call_sheet.status = CallSheetStatus.DRAFT
        db.commit()
    db.refresh(call_sheet)
    return call_sheet


class HeadOfDayNotOnProduction(ValueError):
    """The head of day must be a crew member of this production."""


class CrewCallNotOnProduction(ValueError):
    """A personal call names a crew member of another production (or none)."""


class CastCallNotOnProduction(ValueError):
    """A cast call names a cast member of another production (or none)."""


def _validate_head_of_day(db: Session, production_id, crew_member_id):
    """Return the id if it names a crew member of the production, None if unset.

    Raises:
        HeadOfDayNotOnProduction: the crew member belongs to another production or does not exist.
    """
    if crew_member_id is None:
        return None
    member = db.get(CrewMember, crew_member_id)
    if member is None or member.production_id != production_id:
        raise HeadOfDayNotOnProduction("head of day must be a crew member of this production")
    return crew_member_id


def build_contacts(db: Session, call_sheet: CallSheet) -> CallSheetContacts:
    """The "who to call" section: head of day, heads of department, nearest hospital.

    Computed on read from the crew list and the day's locations, never stored,
    so a phone-number correction in Contacts shows on every sheet at once.
    """
    revision = call_sheet.current_revision

    def card(member: CrewMember) -> ContactCard:
        return ContactCard(
            name=member.contact.name,
            department=member.department,
            position=member.position,
            phone=member.contact.phone,
            email=member.contact.email,
            photo_url=member.contact.photo_url,
        )

    heads = (
        db.query(CrewMember)
        .filter(CrewMember.production_id == call_sheet.production_id, CrewMember.is_head_of_department.is_(True))
        .all()
    )
    heads.sort(key=lambda m: (m.department.lower(), m.contact.name.lower()))

    head_of_day = None
    if revision is not None and revision.head_of_day_crew_member_id is not None:
        member = db.get(CrewMember, revision.head_of_day_crew_member_id)
        if member is not None:
            head_of_day = card(member)

    hospital = None
    if revision is not None:
        for item in sorted(revision.schedule_items, key=lambda i: i.order_index):
            if item.location is not None and item.location.nearest_hospital:
                hospital = item.location.nearest_hospital
                break

    return CallSheetContacts(head_of_day=head_of_day, department_heads=[card(m) for m in heads], nearest_hospital=hospital)


def _crew_entry(revision: CallSheetRevision, member: CrewMember) -> CrewCallEntry | None:
    return next((e for e in revision.crew_calls if e.crew_member_id == member.id), None)


def effective_call(revision: CallSheetRevision, member: CrewMember) -> str | None:
    """When this person is due: today's own entry, then their standing time, then the crew call."""
    entry = _crew_entry(revision, member)
    return (entry.call_time if entry and entry.call_time else None) or member.standard_call_time or revision.general_crew_call


def personal_changes(before: CallSheetRevision | None, after: CallSheetRevision, member: CrewMember) -> list[RevisionChange]:
    """The part of a revision that is about this one person; the push leads with it."""
    if before is None:
        return []
    changes: list[RevisionChange] = []
    was, now = effective_call(before, member), effective_call(after, member)
    if was != now:
        changes.append(RevisionChange(field="your_call", label="Your call", before=was, after=now))
    old, new = _crew_entry(before, member), _crew_entry(after, member)
    was_pickup, now_pickup = old.pickup_time if old else None, new.pickup_time if new else None
    if was_pickup != now_pickup:
        changes.append(RevisionChange(field="your_pickup", label="Your pickup", before=was_pickup, after=now_pickup or "none"))
    was_note, now_note = old.note if old else None, new.note if new else None
    if was_note != now_note and now_note:
        changes.append(RevisionChange(field="your_note", label="Note for you", before=None, after=now_note))
    return changes


def build_personal(db: Session, call_sheet: CallSheet, token: str) -> PersonalSheet | None:
    """The personal block for `?me=<token>`: None when the token is not a crew member of this production."""
    member = (
        db.query(CrewMember)
        .filter(CrewMember.personal_token == token, CrewMember.production_id == call_sheet.production_id)
        .first()
    )
    if member is None:
        return None
    revision = call_sheet.current_revision
    general = revision.general_crew_call if revision is not None else None
    head = (
        db.query(CrewMember)
        .filter(
            CrewMember.production_id == call_sheet.production_id,
            CrewMember.department == member.department,
            CrewMember.is_head_of_department.is_(True),
        )
        .first()
    )
    head_card = None
    if head is not None:
        head_card = ContactCard(name=head.contact.name, department=head.department, position=head.position, phone=head.contact.phone, email=head.contact.email, photo_url=head.contact.photo_url)
    entry = _crew_entry(revision, member) if revision is not None else None
    before = previous_revision(call_sheet)
    call = effective_call(revision, member) if revision is not None else (member.standard_call_time or general)
    was_call = effective_call(before, member) if before is not None else call
    pickup = entry.pickup_time if entry else None
    before_entry = _crew_entry(before, member) if before is not None else None
    was_pickup = before_entry.pickup_time if before_entry else None
    return PersonalSheet(
        name=member.contact.name,
        department=member.department,
        position=member.position,
        personal_call=call,
        pickup_time=pickup,
        note=entry.note if entry else None,
        call_before=was_call if before is not None and was_call != call else None,
        pickup_before=was_pickup if before is not None and was_pickup != pickup else None,
        department_head=head_card,
    )


def previous_revision(call_sheet: CallSheet) -> CallSheetRevision | None:
    """The revision the current one replaced (letters are sequential), or None for a sheet with only REV A."""
    current = call_sheet.current_revision
    if current is None:
        return None
    wanted = chr(ord(current.revision_letter) - 1)
    return next((r for r in call_sheet.revisions if r.revision_letter == wanted), None)


def _ordered_items(revision: CallSheetRevision) -> list[ScheduleItem]:
    return sorted(revision.schedule_items, key=lambda i: i.order_index)


def _scene_order(revision: CallSheetRevision) -> str:
    return ", ".join(item.scene_number for item in _ordered_items(revision))


def _personal_calls_key(revision: CallSheetRevision) -> dict[uuid.UUID, tuple[str | None, str | None, str | None]]:
    return {e.crew_member_id: (e.call_time, e.pickup_time, e.note) for e in revision.crew_calls}


def _keyed_items(revision: CallSheetRevision) -> dict[tuple[str, int], ScheduleItem]:
    """Scenes by (number, nth occurrence): a scene shot in two parts on one day appears twice and must pair up with itself."""
    seen: dict[str, int] = {}
    keyed = {}
    for item in _ordered_items(revision):
        nth = seen.get(item.scene_number, 0)
        seen[item.scene_number] = nth + 1
        keyed[(item.scene_number, nth)] = item
    return keyed


def _pages_label(eighths: int) -> str:
    whole, rest = divmod(eighths, 8)
    if rest == 0:
        return f"{whole} pg"
    return f"{whole} {rest}/8 pg" if whole else f"{rest}/8 pg"


def _scene_detail_change(number: str, old: ScheduleItem, new: ScheduleItem) -> RevisionChange | None:
    """Everything about a scene except where it is shot, only the parts that moved."""
    before, after = [], []
    if old.int_ext != new.int_ext or old.day_night != new.day_night:
        before.append(f"{old.int_ext.value} {old.day_night.value}")
        after.append(f"{new.int_ext.value} {new.day_night.value}")
    if old.set_description != new.set_description:
        before.append(old.set_description)
        after.append(new.set_description)
    if old.page_count_eighths != new.page_count_eighths:
        before.append(_pages_label(old.page_count_eighths))
        after.append(_pages_label(new.page_count_eighths))
    if not after:
        return None
    return RevisionChange(field="scene_detail", label=f"Scene {number}", before=" · ".join(before), after=" · ".join(after), scenes=[number])


def _schedule_changes(before: CallSheetRevision, after: CallSheetRevision) -> list[RevisionChange]:
    old, new = _keyed_items(before), _keyed_items(after)
    common = [k for k in new if k in old]
    changes: list[RevisionChange] = []

    # Grouped, because a rained-out exterior moves several scenes to the same cover set and that is one fact for the crew.
    moved: dict[tuple[str | None, str | None], list[str]] = {}
    for key in common:
        was, now = old[key], new[key]
        if was.location_id != now.location_id:
            names = (was.location.name if was.location else None, now.location.name if now.location else None)
            moved.setdefault(names, []).append(key[0])
    for (was_name, now_name), scenes in moved.items():
        changes.append(RevisionChange(field="location", label=f"Location, sc {', '.join(scenes)}", before=was_name, after=now_name or "no location", scenes=scenes))

    added = [k[0] for k in new if k not in old]
    if added:
        changes.append(RevisionChange(field="scenes_added", label="Scenes added", before=None, after=", ".join(added), scenes=added))
    removed = [k[0] for k in old if k not in new]
    if removed:
        changes.append(RevisionChange(field="scenes_removed", label="Scenes removed", before=None, after=", ".join(removed), scenes=removed))
    for key in common:
        detail = _scene_detail_change(key[0], old[key], new[key])
        if detail is not None:
            changes.append(detail)
    # Only the scenes on both revisions: adding or dropping one is reported above, not as a new shooting order.
    if [k for k in old if k in new] != common:
        changes.append(RevisionChange(field="scene_order", label="Scenes", before=_scene_order(before) or None, after=_scene_order(after) or None))
    return changes


def _cast_changes(before: CallSheetRevision, after: CallSheetRevision) -> list[RevisionChange]:
    def key(revision: CallSheetRevision) -> dict[uuid.UUID, tuple]:
        return {e.cast_member_id: (e.status_code, e.pickup_time, e.call_time, e.makeup_hair_time, e.on_set_time) for e in revision.cast_calls}

    old, new = key(before), key(after)
    entries = {e.cast_member_id: e for e in list(before.cast_calls) + list(after.cast_calls)}
    names = sorted(entries[k].cast_member.contact.name for k in set(old) | set(new) if old.get(k) != new.get(k))
    if not names:
        return []
    return [RevisionChange(field="cast_calls", label="Cast", before=None, after=", ".join(names))]


def revision_changes(before: CallSheetRevision | None, after: CallSheetRevision) -> list[RevisionChange]:
    """What a crew member who read `before` last night needs to know about `after` (FR-23, FR-200).

    Covers every field a revision carries, most consequential first, so an
    empty list means the content really is identical: the push may only say
    "no changes" when that is true. test_revision_diff.py fails when a new
    revision field is added without being compared here.
    """
    if before is None:
        return []
    changes: list[RevisionChange] = []
    for field, label, attr in (("crew_call", "Crew call", "general_crew_call"), ("shooting_call", "Shooting call", "shooting_call")):
        old, new = getattr(before, attr), getattr(after, attr)
        if (old or None) != (new or None):
            changes.append(RevisionChange(field=field, label=label, before=old, after=new))
    changes.extend(_schedule_changes(before, after))
    if (before.safety_notes or None) != (after.safety_notes or None):
        changes.append(RevisionChange(field="safety_notes", label="Safety", before=before.safety_notes, after=after.safety_notes))
    changes.extend(_cast_changes(before, after))
    old_pc, new_pc = _personal_calls_key(before), _personal_calls_key(after)
    moved = sum(1 for k in set(old_pc) | set(new_pc) if old_pc.get(k) != new_pc.get(k))
    if moved:
        changes.append(RevisionChange(field="personal_calls", label="Personal calls", before=None, after=f"{moved} changed"))
    if before.head_of_day_crew_member_id != after.head_of_day_crew_member_id:
        changes.append(RevisionChange(
            field="head_of_day", label="Head of day",
            before=before.head_of_day.contact.name if before.head_of_day else None,
            after=after.head_of_day.contact.name if after.head_of_day else "not set",
        ))
    for field, label, attr in (("weather", "Weather", "weather_forecast"), ("sunrise", "Sunrise", "sunrise"), ("sunset", "Sunset", "sunset")):
        old, new = getattr(before, attr), getattr(after, attr)
        if (old or None) != (new or None):
            changes.append(RevisionChange(field=field, label=label, before=old, after=new))
    return changes


_PUSH_VALUE_LIMIT = 60


def _push_value(value: str | None) -> str:
    if not value:
        return "—"
    return value if len(value) <= _PUSH_VALUE_LIMIT else f"{value[:_PUSH_VALUE_LIMIT - 1]}…"


def change_summary(changes: list[RevisionChange]) -> str:
    """One line for a push notification: the first two changes, then how many more."""
    if not changes:
        return "republished, content unchanged"
    parts = []
    for c in changes[:2]:
        if c.before is None:
            parts.append(f"{c.label.lower()}: {_push_value(c.after)}")
        else:
            parts.append(f"{c.label.lower()} {_push_value(c.before)} → {_push_value(c.after)}")
    more = len(changes) - 2
    return "; ".join(parts) + (f" (+{more} more)" if more > 0 else "")


def build_sheet_locations(db: Session, call_sheet: CallSheet) -> list[SheetLocation]:
    """The day's locations in the order the schedule reaches them, each with the scenes shot there (FR-35).

    Read live from the Locations tab, never stored on the revision: a corrected address or parking note
    reaches every sheet at once, the same rule as contacts. A scene whose location was deleted is skipped."""
    revision = call_sheet.current_revision
    if revision is None:
        return []
    out: list[SheetLocation] = []
    by_id: dict[uuid.UUID, SheetLocation] = {}
    for item in sorted(revision.schedule_items, key=lambda i: i.order_index):
        if item.location_id is None:
            continue
        entry = by_id.get(item.location_id)
        if entry is None:
            loc = db.get(Location, item.location_id)
            if loc is None:
                continue
            entry = SheetLocation(id=loc.id, name=loc.name, address=loc.address, parking_notes=loc.parking_notes, nearest_hospital=loc.nearest_hospital,
                                  geo_lat=loc.geo_lat, geo_lng=loc.geo_lng, scene_numbers=[])
            by_id[loc.id] = entry
            out.append(entry)
        if item.scene_number and item.scene_number not in entry.scene_numbers:
            entry.scene_numbers.append(item.scene_number)
    return out


def build_cast_calls(db: Session, call_sheet: CallSheet) -> list[CastCallRow]:
    """Named cast lines for the sheet, in call-time order then by name (the sheet reads top to bottom as the day starts)."""
    revision = call_sheet.current_revision
    if revision is None:
        return []
    rows = []
    for e in revision.cast_calls:
        actor = db.get(CastMember, e.cast_member_id)
        if actor is None:
            continue
        rows.append(CastCallRow(cast_member_id=actor.id, name=actor.contact.name, character_name=actor.character_name, status_code=e.status_code,
                                pickup_time=e.pickup_time, call_time=e.call_time, makeup_hair_time=e.makeup_hair_time, on_set_time=e.on_set_time))
    rows.sort(key=lambda r: (r.call_time or r.pickup_time or "99:99", r.name.lower()))
    return rows


def build_personal_calls(db: Session, call_sheet: CallSheet) -> list[PersonalCallRow]:
    """Named rows for the printed personal-calls table, in crew-list order (department, name)."""
    revision = call_sheet.current_revision
    if revision is None:
        return []
    rows = []
    for e in revision.crew_calls:
        m = db.get(CrewMember, e.crew_member_id)
        if m is None:
            continue
        rows.append(PersonalCallRow(crew_member_id=m.id, name=m.contact.name, department=m.department, position=m.position,
                                    call_time=e.call_time, pickup_time=e.pickup_time, note=e.note))
    rows.sort(key=lambda r: (r.department.lower(), r.name.lower()))
    return rows


def next_day_for_token(db: Session, token: str, today: date) -> CrewNextDay | None:
    """FR-32: one link per person for the whole shoot. Resolves the personal
    token to its crew member and picks the day that link should open: the
    earliest shoot day on or after `today`, else the most recent one (the
    shoot is over, the last sheet is still the useful one). None for an
    unknown token; a production with no days yet gives call_sheet_id None
    so the viewer can say "no day published yet" instead of 404-ing."""
    member = db.query(CrewMember).filter(CrewMember.personal_token == token).first()
    if member is None:
        return None
    sheets = (
        db.query(CallSheet)
        .filter(CallSheet.production_id == member.production_id)
        .order_by(CallSheet.shoot_date, CallSheet.day_number)
        .all()
    )
    def first_location_name(revision: CallSheetRevision | None) -> str | None:
        if revision is None:
            return None
        for item in sorted(revision.schedule_items, key=lambda i: i.order_index):
            if item.location_id is not None:
                loc = db.get(Location, item.location_id)
                if loc is not None:
                    return loc.name
        return None

    days = [
        CrewDayRef(call_sheet_id=s.id, shoot_date=s.shoot_date, day_number=s.day_number, day_count=s.day_count, unit_name=s.unit_name,
                   revision_letter=s.current_revision.revision_letter if s.current_revision else None, status=s.status.value,
                   general_crew_call=s.current_revision.general_crew_call if s.current_revision else None,
                   first_location_name=first_location_name(s.current_revision))
        for s in sheets
    ]
    days = [d for d in days if d.status != "draft"]  # planned days (FR-56) do not exist for the crew yet
    live = [d for d in days if d.status != "cancelled"]
    upcoming = [d for d in live if d.shoot_date >= today]
    chosen = upcoming[0] if upcoming else (live[-1] if live else (days[-1] if days else None))
    return CrewNextDay(production_name=member.production.name, crew_member_name=member.contact.name,
                       call_sheet_id=chosen.call_sheet_id if chosen else None, days=days)


def record_seen(db: Session, call_sheet: CallSheet, token: str) -> bool:
    """FR-36: a crew member's personal link loaded the current revision live. False for an unknown token."""
    revision = call_sheet.current_revision
    member = (
        db.query(CrewMember)
        .filter(CrewMember.personal_token == token, CrewMember.production_id == call_sheet.production_id)
        .first()
    )
    if revision is None or member is None:
        return False
    view = db.query(RevisionView).filter(RevisionView.revision_id == revision.id, RevisionView.crew_member_id == member.id).first()
    if view is None:
        db.add(RevisionView(revision_id=revision.id, crew_member_id=member.id))
    else:
        view.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return True


def build_seen_report(db: Session, call_sheet: CallSheet) -> SeenReport | None:
    """Who has opened the current revision and who has not, so the AD chases the right people (FR-36)."""
    revision = call_sheet.current_revision
    if revision is None:
        return None
    views = {v.crew_member_id: v.first_seen_at for v in db.query(RevisionView).filter(RevisionView.revision_id == revision.id).all()}
    subscribed = {s.crew_member_id for s in db.query(PushSubscription).join(CrewMember, CrewMember.id == PushSubscription.crew_member_id)
                  .filter(CrewMember.production_id == call_sheet.production_id).all()}
    crew = db.query(CrewMember).filter(CrewMember.production_id == call_sheet.production_id).all()
    crew.sort(key=lambda m: (m.department.lower(), m.contact.name.lower()))
    entries = [
        SeenEntry(crew_member_id=m.id, name=m.contact.name, department=m.department, position=m.position, phone=m.contact.phone,
                  personal_token=m.personal_token, seen_at=views.get(m.id), subscribed=m.id in subscribed)
        for m in crew
    ]
    return SeenReport(revision_letter=revision.revision_letter,
                      seen=[e for e in entries if e.seen_at is not None], not_seen=[e for e in entries if e.seen_at is None])


def build_history(db: Session, call_sheet: CallSheet) -> list[HistoryEntry]:
    """FR-50: one line per revision — who published it, when, what it changed
    versus the one before, and how many crew have opened it. `call_sheet.revisions`
    is already ordered oldest-first (the relationship's own order_by), so each
    entry only needs the revision immediately before it in that same list.

    Cancel/restore is not recorded here: no `call_sheet_events` model exists
    yet to carry it, so the dod's own instruction is followed literally —
    left out rather than guessed at."""
    revisions = call_sheet.revisions
    entries = []
    for i, revision in enumerate(revisions):
        before = revisions[i - 1] if i > 0 else None
        opened = db.query(RevisionView).filter(RevisionView.revision_id == revision.id).count()
        entries.append(HistoryEntry(
            revision_letter=revision.revision_letter,
            created_at=revision.created_at,
            created_by=revision.created_by or "unknown",
            changes=revision_changes(before, revision),
            opened=opened,
            notifications=_push_summary_for_revision(db, revision.id),
        ))
    return entries


def _push_summary_for_revision(db: Session, revision_id: uuid.UUID) -> NotificationSummaryRead | None:
    """FR-78: push delivery moved to a background task run after the publish
    response is sent (app/services/notifications.py's *_in_background wrappers),
    so the AD checks it here rather than in that response. Reads the same
    DistributionLog rows the delivery loop itself writes; None means no attempt
    is on record yet (still in flight, push not configured, or nobody subscribed)."""
    rows = (
        db.query(DistributionLog)
        .filter(DistributionLog.revision_id == revision_id, DistributionLog.channel == DistributionChannel.PUSH)
        .all()
    )
    if not rows:
        return None
    failed = [DeliveryFailureRead(crew_member_name=row.contact.name, reason=row.error) for row in rows if row.error is not None]
    return NotificationSummaryRead(attempted=len(rows), delivered=len(rows) - len(failed), failed=failed)


def build_opened_summary(db: Session, call_sheet: CallSheet) -> OpenedSummary | None:
    """FR-43: the days list at a glance — opened by 3 of 12, and where the day starts."""
    revision = call_sheet.current_revision
    if revision is None:
        return None
    seen = db.query(RevisionView).filter(RevisionView.revision_id == revision.id).count()
    total = db.query(CrewMember).filter(CrewMember.production_id == call_sheet.production_id).count()
    first = next((i for i in sorted(revision.schedule_items, key=lambda i: i.order_index) if i.location_id is not None), None)
    loc = db.get(Location, first.location_id) if first is not None else None
    return OpenedSummary(seen=seen, total=total, first_location_name=loc.name if loc is not None else None)

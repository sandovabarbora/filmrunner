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

from sqlalchemy import or_, text, update
from sqlalchemy.dialects.postgresql import insert
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


class StaleRevision(ValueError):
    """The day moved on since this publish was prepared, and publishing would overwrite someone else's change."""


def _rows_match(payload_rows, stored_rows, key) -> bool:
    if len(payload_rows) != len(stored_rows):
        return False
    return all(
        all(getattr(stored, field) == value for field, value in sent.model_dump().items())
        for sent, stored in zip(sorted(payload_rows, key=key), sorted(stored_rows, key=key))
    )


def _is_same_content(revision: CallSheetRevision, previous: CallSheetRevision | None, payload: CallSheetRevisionCreate) -> bool:
    """Tells a retry of the same publish from a different edit. The server fills some blank fields in, so a blank
    matches a stored value, unless the revision before had a value: then the blank is someone clearing it."""
    for field in ("general_crew_call", "shooting_call", "safety_notes", "head_of_day_crew_member_id"):
        if getattr(revision, field) != getattr(payload, field):
            return False
    for field in ("sunrise", "sunset", "weather_forecast"):
        sent = getattr(payload, field) or None
        stored = getattr(revision, field) or None
        cleared = sent is None and previous is not None and getattr(previous, field)
        if (sent is not None and stored != sent) or (cleared and stored is not None):
            return False
    if not _rows_match(payload.schedule_items, revision.schedule_items, key=lambda r: r.order_index):
        return False
    if payload.crew_calls is not None and not _rows_match(payload.crew_calls, revision.crew_calls, key=lambda r: str(r.crew_member_id)):
        return False
    return payload.cast_calls is None or _rows_match(payload.cast_calls, revision.cast_calls, key=lambda r: str(r.cast_member_id))


def _next_revision_letter(call_sheet: CallSheet) -> str:
    """Return the next revision letter for a call sheet.

    Raises:
        ValueError: if more than 26 revisions are requested in one day —
            at that point something upstream is broken and silently
            wrapping to "AA" would hide it.
    """
    count = len(call_sheet.revisions)
    if count >= len(_REVISION_LETTERS):
        # The routers return this text to the AD as a 409, so it says what to do next and carries no ids.
        raise ValueError(
            f"Day {call_sheet.day_number} already has {count} revisions (REV A to Z), the most one day can have. "
            "To change it further, cancel this day and create a new one for the same date."
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


def _weather_target(db: Session, revision: CallSheetRevision) -> tuple[float, float, date] | None:
    # Open-Meteo forecasts 16 days ahead and nothing in the past; outside that window the call can only
    # fail (FR-52 found a 400 per publish on a 30-day schedule import), so it is not made.
    horizon = (revision.shoot_date - date.today()).days
    if horizon < 0 or horizon > 16:
        return None
    ordered = sorted((i for i in revision.schedule_items if i.location_id is not None), key=lambda i: i.order_index)
    if not ordered:
        return None
    location = db.get(Location, ordered[0].location_id)
    if location is None or location.geo_lat is None or location.geo_lng is None or location.production.sandbox_session is not None:
        return None
    return location.geo_lat, location.geo_lng, revision.shoot_date


def fill_weather_after_commit(db: Session, revision: CallSheetRevision) -> None:
    """FR-39: a blank weather line reads as "not checked", so it fills from the day's first located scene,
    the same text the "Suggest weather" button gives, and never replaces a value someone wrote.

    FR-223: call only after the publish is committed, so a slow provider holds neither the advisory lock nor
    a pooled connection. The publish already stands at this point, so nothing here may turn it into an error.
    """
    if revision.weather_forecast:
        return
    revision_id = revision.id
    try:
        target = _weather_target(db, revision)
        db.commit()  # ends the read above: no connection stays checked out across the HTTP call
        if target is None:
            return
        suggestion = weather.weather_suggestion(*target)
        if suggestion is None:
            return
        db.execute(
            update(CallSheetRevision)
            .where(
                CallSheetRevision.id == revision_id,
                CallSheetRevision.is_current.is_(True),  # a revision superseded during the call keeps what the crew saw on it
                or_(CallSheetRevision.weather_forecast.is_(None), CallSheetRevision.weather_forecast == ""),
            )
            .values(weather_forecast=suggestion)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - see the docstring
        db.rollback()
        logger.warning("Weather fill failed for revision %s: %s", revision_id, exc.__class__.__name__)


def publish_revision(
    db: Session, call_sheet: CallSheet, payload: CallSheetRevisionCreate, created_by: str | None = None, commit: bool = True
) -> tuple[CallSheetRevision, bool]:
    """Create a new revision on an existing call sheet, marking prior
    revisions as no longer current.

    This is the "hot revision" operation: same-day corrections happen by
    adding a new immutable revision, never by editing an existing one — see
    DESIGN.md for why.

    Returns (revision, is_new). A Postgres transaction-scoped advisory lock
    serializes publishes of one call sheet. FR-142: a double-tap or a retry
    after a lost response sends the same content twice, and collapses into
    the revision already published, with is_new=False; the caller must not
    send a second push then. FR-219: anything else that lost the race, or
    that was prepared from another revision than `expected_revision_id`
    says, is a different person's edit and raises StaleRevision, since
    publishing it would silently undo the change that won.

    `commit=False` leaves the transaction open for a change spanning several
    days (app/services/replan.py); its advisory lock is held until that commit,
    and the caller then calls fill_weather_after_commit itself.
    """
    # By id, not by count or letter: publishing a planned day replaces its REV A with a new REV A.
    before_lock = call_sheet.current_revision.id if call_sheet.current_revision is not None else None
    lock_key = str(call_sheet.id)
    waited = not db.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": lock_key}
    ).scalar()
    if waited:
        # The lock releases at the end of the other publish's transaction.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": lock_key})
    # Only these two: a change spanning days has unflushed edits on this object, and the session does not autoflush.
    db.expire(call_sheet, ["revisions", "status"])
    current = call_sheet.current_revision
    current_id = current.id if current is not None else None
    lost_the_race = current_id != before_lock
    prepared_from_older = payload.expected_revision_id is not None and current_id != payload.expected_revision_id
    if (lost_the_race or prepared_from_older) and current is not None:
        earlier = sorted((r for r in call_sheet.revisions if r.id != current.id), key=lambda r: r.revision_letter)
        if _is_same_content(current, earlier[-1] if earlier else None, payload):
            return current, False
        raise StaleRevision(f"REV {current.revision_letter} was published after this was prepared, so nothing was published. Reload the day and make the change again.")

    head_of_day_id = _validate_head_of_day(db, call_sheet.production_id, payload.head_of_day_crew_member_id)
    previous = call_sheet.current_revision
    if call_sheet.hidden_from_crew and previous is not None:
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
    named_locations = {item.location_id for item in payload.schedule_items if item.location_id is not None}
    if named_locations:
        own = {r[0] for r in db.query(Location.id).filter(Location.production_id == call_sheet.production_id, Location.id.in_(named_locations))}
        if named_locations - own:
            raise LocationNotOnProduction("scenes must use locations of this production")

    if payload.crew_calls is None:
        # Copy forward: the AD edits yesterday's personal calls, they never retype them.
        # model_construct, here and below: a stored value is not new input, and an old one must not block a publish that does not touch it.
        crew_calls = [
            CrewCallEntryCreate.model_construct(crew_member_id=e.crew_member_id, call_time=e.call_time, pickup_time=e.pickup_time, note=e.note)
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
            CastCallEntryCreate.model_construct(cast_member_id=e.cast_member_id, status_code=e.status_code, pickup_time=e.pickup_time,
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
    call_sheet.cancelled_from_draft = False

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
        shoot_date=call_sheet.shoot_date,
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

    if commit:
        db.commit()
        fill_weather_after_commit(db, revision)
    else:
        db.flush()
    db.refresh(revision)
    logger.info(
        "Published revision %s for call sheet %s (%d schedule items, %d cast calls)",
        revision.revision_letter,
        call_sheet.id,
        len(payload.schedule_items),
        len(cast_calls),
    )
    return revision, True


class DuplicateDay(ValueError):
    """This date, day number and unit is already a day, with other content; the message tells the AD."""


def live_days_like(db: Session, production_id, shoot_date: date, day_number: int, unit_name: str) -> list[CallSheet]:
    """The days this one would duplicate. A cancelled day does not count: creating its replacement is the normal way forward."""
    return (
        db.query(CallSheet)
        .filter(CallSheet.production_id == production_id, CallSheet.shoot_date == shoot_date, CallSheet.day_number == day_number,
                CallSheet.unit_name == unit_name, CallSheet.status != CallSheetStatus.CANCELLED)
        .all()
    )


def _same_create_request(sheet: CallSheet, payload: CallSheetCreate) -> bool:
    """Whether `payload` is what created `sheet`, so a retry rather than a second day. Compared with REV A, not the
    current revision: a retry that arrives after a newer publish is still that same request."""
    first = next((r for r in sheet.revisions if r.revision_letter == "A"), None)
    wanted = payload.initial_revision
    if first is None or sheet.day_count != payload.day_count or (sheet.status == CallSheetStatus.DRAFT) != payload.draft:
        return False
    # Left blank, these were filled in by the server when it published.
    if any(getattr(wanted, name) and getattr(wanted, name) != getattr(first, name) for name in ("sunrise", "sunset", "weather_forecast")):
        return False
    if any((getattr(wanted, name) or None) != (getattr(first, name) or None) for name in ("general_crew_call", "shooting_call", "safety_notes", "head_of_day_crew_member_id")):
        return False
    stored_items = [(i.order_index, i.scene_number, i.int_ext, i.day_night, i.set_description, i.location_id, i.page_count_eighths) for i in _ordered_items(first)]
    sent_items = sorted(((i.order_index, i.scene_number, i.int_ext, i.day_night, i.set_description, i.location_id, i.page_count_eighths) for i in wanted.schedule_items), key=lambda row: row[0])
    stored_crew = {e.crew_member_id: (e.call_time, e.pickup_time, e.note) for e in first.crew_calls}
    sent_crew = {e.crew_member_id: (e.call_time, e.pickup_time, e.note) for e in wanted.crew_calls or []}
    stored_cast = {e.cast_member_id: (e.status_code, e.pickup_time, e.call_time, e.makeup_hair_time, e.on_set_time) for e in first.cast_calls}
    sent_cast = {e.cast_member_id: (e.status_code, e.pickup_time, e.call_time, e.makeup_hair_time, e.on_set_time) for e in wanted.cast_calls or []}
    return stored_items == sent_items and stored_crew == sent_crew and stored_cast == sent_cast


def create_call_sheet_once(db: Session, production_id, payload: CallSheetCreate, created_by: str | None = None) -> tuple[CallSheet, bool]:
    """Create a day unless it exists. Returns (day, is_new); is_new False is a retry, and the crew was told the first time.

    An advisory lock rather than a unique index: an index cannot be added while older duplicates may exist, and a
    retried create has to be told apart from a real conflict anyway.

    Raises:
        DuplicateDay: the day exists with other content.
    """
    key = f"create-day:{production_id}:{payload.shoot_date}:{payload.day_number}:{payload.unit_name}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": key})
    existing = live_days_like(db, production_id, payload.shoot_date, payload.day_number, payload.unit_name)
    if not existing:
        return create_call_sheet(db, production_id, payload, created_by=created_by), True
    retried = next((sheet for sheet in existing if _same_create_request(sheet, payload)), None)
    if retried is not None:
        return retried, False
    raise DuplicateDay(f"Day {payload.day_number} of {payload.unit_name} on {payload.shoot_date.isoformat()} already exists; open it instead of creating it again")


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

    # Not committed yet: a draft must never be visible as published, not even while the forecast loads.
    revision, _ = publish_revision(db, call_sheet, payload.initial_revision, created_by=created_by, commit=False)
    if payload.draft:
        call_sheet.status = CallSheetStatus.DRAFT
    db.commit()
    fill_weather_after_commit(db, revision)
    db.refresh(call_sheet)
    return call_sheet


class HeadOfDayNotOnProduction(ValueError):
    """The head of day must be a crew member of this production."""


class LocationNotOnProduction(ValueError):
    """A scene names a location of another production; the public sheet would show that location."""


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
    if was_note != now_note:
        changes.append(RevisionChange(field="your_note", label="Note for you", before=was_note, after=now_note or "removed"))
    return changes


def _last_read_revision(db: Session, call_sheet: CallSheet, member: CrewMember | CastMember) -> CallSheetRevision | None:
    """FR-204: what this person actually knows, when that is older than the revision before the current one. Someone
    who read REV B and opens REV D needs B to D, or C's change never reaches them. The last one they confirmed if
    any, since that is their own word; otherwise the last they opened. None when the normal diff already covers it."""
    current = call_sheet.current_revision
    previous = previous_revision(call_sheet)
    if current is None or previous is None:
        return None
    current_view = _view_of(db, current, member)
    if current_view is not None and current_view.confirmed_at is not None:
        return None
    day_revisions = [r.id for r in call_sheet.revisions]
    views = {v.revision_id: v for v in db.query(RevisionView).filter(_view_column(member) == member.id, RevisionView.revision_id.in_(day_revisions)).all()}
    earlier = [r for r in call_sheet.revisions if r.revision_letter < current.revision_letter and r.id in views]
    confirmed = [r for r in earlier if views[r.id].confirmed_at is not None]
    known = confirmed or earlier
    if not known:
        return None
    baseline = max(known, key=lambda r: r.revision_letter)
    return baseline if baseline.id != previous.id else None


def _person_on_production(db: Session, production_id, token: str) -> CrewMember | CastMember | None:
    """Whoever this personal link belongs to on this production. A token from another production is nobody here."""
    crew = db.query(CrewMember).filter(CrewMember.personal_token == token, CrewMember.production_id == production_id).first()
    if crew is not None:
        return crew
    return db.query(CastMember).filter(CastMember.personal_token == token, CastMember.production_id == production_id).first()


def _view_column(person: CrewMember | CastMember):
    return RevisionView.cast_member_id if isinstance(person, CastMember) else RevisionView.crew_member_id


def _view_of(db: Session, revision: CallSheetRevision, person: CrewMember | CastMember) -> RevisionView | None:
    return db.query(RevisionView).filter(RevisionView.revision_id == revision.id, _view_column(person) == person.id).first()


def _ensure_view(db: Session, revision: CallSheetRevision, person: CrewMember | CastMember) -> RevisionView:
    """The person's receipt, created if needed. The page load's receipt and a quick tap on confirm arrive together,
    so "look, then insert" would fail on the unique constraint; the insert itself has to tolerate losing that race."""
    who = {"cast_member_id": person.id} if isinstance(person, CastMember) else {"crew_member_id": person.id}
    db.execute(insert(RevisionView).values(id=uuid.uuid4(), revision_id=revision.id, **who).on_conflict_do_nothing())
    view = _view_of(db, revision, person)
    assert view is not None  # just inserted, or the row that won the race
    return view


def _build_cast_personal(db: Session, call_sheet: CallSheet, actor: CastMember) -> PersonalSheet:
    """An actor's block: their own times from the day's cast call. Never the crew call: that is not when they are due."""
    revision = call_sheet.current_revision

    def entry_on(rev: CallSheetRevision | None) -> CastCallEntry | None:
        return next((e for e in rev.cast_calls if e.cast_member_id == actor.id), None) if rev is not None else None

    entry = entry_on(revision)
    caught_up_from = _last_read_revision(db, call_sheet, actor) if revision is not None else None
    before = caught_up_from or previous_revision(call_sheet)
    was = entry_on(before)
    view = _view_of(db, revision, actor) if revision is not None else None
    call, pickup = entry.call_time if entry else None, entry.pickup_time if entry else None
    return PersonalSheet(
        name=actor.contact.name,
        department="Cast",
        position=actor.character_name,
        personal_call=call,
        pickup_time=pickup,
        makeup_hair_time=entry.makeup_hair_time if entry else None,
        on_set_time=entry.on_set_time if entry else None,
        is_cast=True,
        works_today=entry is not None,
        call_before=was.call_time if was is not None and was.call_time != call else None,
        pickup_before=was.pickup_time if was is not None and was.pickup_time != pickup else None,
        revision_letter=revision.revision_letter if revision is not None else None,
        confirmed_at=view.confirmed_at if view is not None else None,
        since_letter=caught_up_from.revision_letter if caught_up_from is not None else None,
        changes_since=revision_changes(caught_up_from, revision) if caught_up_from is not None else None,
        department_head=None,
    )


def build_personal(db: Session, call_sheet: CallSheet, token: str) -> PersonalSheet | None:
    """The personal block for `?me=<token>`: None when the token is not a crew member of this production."""
    member = _person_on_production(db, call_sheet.production_id, token)
    if member is None:
        return None
    if isinstance(member, CastMember):
        return _build_cast_personal(db, call_sheet, member)
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
    caught_up_from = _last_read_revision(db, call_sheet, member) if revision is not None else None
    before = caught_up_from or previous_revision(call_sheet)
    call = effective_call(revision, member) if revision is not None else (member.standard_call_time or general)
    was_call = effective_call(before, member) if before is not None else call
    pickup = entry.pickup_time if entry else None
    view = _view_of(db, revision, member) if revision is not None else None
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
        note_changed=before is not None and (before_entry.note if before_entry else None) != (entry.note if entry else None),
        revision_letter=revision.revision_letter if revision is not None else None,
        confirmed_at=view.confirmed_at if view is not None else None,
        since_letter=caught_up_from.revision_letter if caught_up_from is not None else None,
        changes_since=revision_changes(caught_up_from, revision) if caught_up_from is not None else None,
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


def _move_change(field: str, label: str, scene_number: str, other: CallSheetRevision) -> RevisionChange:
    sheet = other.call_sheet
    where = f"Day {sheet.day_number}, {sheet.shoot_date.isoformat()}"
    return RevisionChange(field=field, label=label, before=None, after=where, scenes=[scene_number],
                          other_call_sheet_id=sheet.id, other_day_number=sheet.day_number, other_date=sheet.shoot_date.isoformat())


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

    # A recorded move says where the scene went; it is not also a scene that appeared or vanished.
    # Every revision since `before`, not only the last: someone catching up across several must still see each move.
    between = [r for r in after.call_sheet.revisions if before.revision_letter < r.revision_letter <= after.revision_letter]
    # A planned day does not exist for the crew: no link to it and no trace of it. To them the scene simply left or arrived.
    moves_out = [m for r in between for m in r.moves_out if not m.to_revision.call_sheet.hidden_from_crew]
    moves_in = [m for r in between for m in r.moves_in if not m.from_revision.call_sheet.hidden_from_crew]
    moved_out = {m.scene_number for m in moves_out}
    moved_in = {m.scene_number for m in moves_in}
    for move in moves_out:
        changes.append(_move_change("scene_moved_out", f"Scene {move.scene_number} moved to", move.scene_number, move.to_revision))
    for move in moves_in:
        changes.append(_move_change("scene_moved_in", f"Scene {move.scene_number} moved from", move.scene_number, move.from_revision))

    added = [k[0] for k in new if k not in old and k[0] not in moved_in]
    if added:
        changes.append(RevisionChange(field="scenes_added", label="Scenes added", before=None, after=", ".join(added), scenes=added))
    removed = [k[0] for k in old if k not in new and k[0] not in moved_out]
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
    if before.shoot_date and after.shoot_date and before.shoot_date != after.shoot_date:
        changes.append(RevisionChange(field="shoot_date", label="Date", before=before.shoot_date.isoformat(), after=after.shoot_date.isoformat()))
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
        if c.field in ("scene_moved_out", "scene_moved_in"):
            parts.append(f"{c.label.lower()} {c.after}")
        elif c.before is None:
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
    member = db.query(CrewMember).filter(CrewMember.personal_token == token).first() or db.query(CastMember).filter(CastMember.personal_token == token).first()
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
        if not s.hidden_from_crew
    ]
    live = [d for d in days if d.status != "cancelled"]
    upcoming = [d for d in live if d.shoot_date >= today]
    chosen = upcoming[0] if upcoming else (live[-1] if live else (days[-1] if days else None))
    return CrewNextDay(production_name=member.production.name, crew_member_name=member.contact.name,
                       call_sheet_id=chosen.call_sheet_id if chosen else None, days=days)


def record_seen(db: Session, call_sheet: CallSheet, token: str) -> bool:
    """FR-36: a crew member's personal link loaded the current revision live. False for an unknown token."""
    revision = call_sheet.current_revision
    person = _person_on_production(db, call_sheet.production_id, token)
    if revision is None or person is None:
        return False
    if not _is_called(revision, person):
        return True  # a real link, but counting it would push the AD's "opened" past the number of people on the list
    _ensure_view(db, revision, person).last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return True


class NotCalledToday(ValueError):
    """An actor with no call on this day has nothing to confirm, and is not on the AD's list for it."""


def _is_called(revision: CallSheetRevision, person: CrewMember | CastMember) -> bool:
    """Crew are on every day's list; an actor only on the days they are called."""
    return not isinstance(person, CastMember) or any(e.cast_member_id == person.id for e in revision.cast_calls)


class RevisionNoLongerCurrent(ValueError):
    """The person confirmed a revision that a newer one has replaced: they have not read the current one."""


def record_confirmed(db: Session, call_sheet: CallSheet, token: str, revision_letter: str) -> datetime | None:
    """FR-202: a crew member confirms the revision they are looking at. Keeps the first confirmation; None for an unknown token.

    Raises:
        RevisionNoLongerCurrent: `revision_letter` is not the current revision, so "I know" would be about an old plan.
    """
    revision = call_sheet.current_revision
    person = _person_on_production(db, call_sheet.production_id, token)
    if revision is None or person is None:
        return None
    if revision.revision_letter != revision_letter:
        raise RevisionNoLongerCurrent(f"REV {revision_letter} has been replaced by REV {revision.revision_letter}")
    if not _is_called(revision, person):
        raise NotCalledToday("You are not called on this day; there is nothing to confirm")
    view = _ensure_view(db, revision, person)
    if view.confirmed_at is None:
        view.confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return view.confirmed_at


def build_seen_report(db: Session, call_sheet: CallSheet) -> SeenReport | None:
    """Who has opened the current revision and who has not, so the AD chases the right people (FR-36)."""
    revision = call_sheet.current_revision
    if revision is None:
        return None
    rows = db.query(RevisionView).filter(RevisionView.revision_id == revision.id).all()
    views = {v.crew_member_id or v.cast_member_id: v.first_seen_at for v in rows}
    confirmed = {v.crew_member_id or v.cast_member_id: v.confirmed_at for v in rows}
    subscribed = {s.crew_member_id for s in db.query(PushSubscription).join(CrewMember, CrewMember.id == PushSubscription.crew_member_id)
                  .filter(CrewMember.production_id == call_sheet.production_id).all()}
    crew = db.query(CrewMember).filter(CrewMember.production_id == call_sheet.production_id).all()
    crew.sort(key=lambda m: (m.department.lower(), m.contact.name.lower()))
    entries = [
        SeenEntry(crew_member_id=m.id, name=m.contact.name, department=m.department, position=m.position, phone=m.contact.phone,
                  personal_token=m.personal_token, seen_at=views.get(m.id), confirmed_at=confirmed.get(m.id), subscribed=m.id in subscribed)
        for m in crew
    ]
    # An actor is on the list for the days they are called, not for the whole shoot.
    called = sorted((e.cast_member for e in revision.cast_calls), key=lambda a: a.contact.name.lower())
    entries += [
        SeenEntry(crew_member_id=a.id, name=a.contact.name, department="Cast", position=a.character_name, phone=a.contact.phone,
                  personal_token=a.personal_token, seen_at=views.get(a.id), confirmed_at=confirmed.get(a.id), subscribed=False, is_cast=True)
        for a in called
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
    confirmed = db.query(RevisionView).filter(RevisionView.revision_id == revision.id, RevisionView.confirmed_at.is_not(None)).count()
    total = db.query(CrewMember).filter(CrewMember.production_id == call_sheet.production_id).count() + len(revision.cast_calls)
    first = next((i for i in sorted(revision.schedule_items, key=lambda i: i.order_index) if i.location_id is not None), None)
    loc = db.get(Location, first.location_id) if first is not None else None
    return OpenedSummary(seen=seen, confirmed=confirmed, total=total, first_location_name=loc.name if loc is not None else None)

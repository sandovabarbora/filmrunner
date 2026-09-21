"""Business logic for publishing call-sheet revisions.

Kept separate from the router (I/O layer) per the "separate business logic
from I/O" standard — this module has no FastAPI imports and is unit-testable
without spinning up the HTTP layer.

Reference: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
"""

import logging
import string
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.production import CrewMember, Location
from app.models.call_sheet import CallSheet, CallSheetRevision, CastCallEntry, CrewCallEntry, ScheduleItem
from app.schemas.call_sheet import CallSheetContacts, ContactCard, CrewCallEntryCreate, CrewDayRef, CrewNextDay, PersonalCallRow, PersonalSheet, CallSheetCreate, CallSheetRevisionCreate, RevisionChange, RevisionSummary
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


def publish_revision(
    db: Session, call_sheet: CallSheet, payload: CallSheetRevisionCreate, created_by: str | None = None
) -> CallSheetRevision:
    """Create a new revision on an existing call sheet, marking prior
    revisions as no longer current.

    This is the "hot revision" operation: same-day corrections happen by
    adding a new immutable revision, never by editing an existing one — see
    DESIGN.md for why.
    """
    head_of_day_id = _validate_head_of_day(db, call_sheet.production_id, payload.head_of_day_crew_member_id)
    previous = call_sheet.current_revision
    if payload.crew_calls is None:
        # Copy forward: the AD edits yesterday's personal calls, they never retype them.
        crew_calls = [
            CrewCallEntryCreate(crew_member_id=e.crew_member_id, call_time=e.call_time, pickup_time=e.pickup_time, note=e.note)
            for e in (previous.crew_calls if previous is not None else [])
            if db.get(CrewMember, e.crew_member_id) is not None
        ]
    else:
        crew_calls = payload.crew_calls
        for entry in crew_calls:
            member = db.get(CrewMember, entry.crew_member_id)
            if member is None or member.production_id != call_sheet.production_id:
                raise CrewCallNotOnProduction("personal calls must name crew members of this production")

    for existing in call_sheet.revisions:
        existing.is_current = False

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
    for cast_call in payload.cast_calls:
        db.add(CastCallEntry(revision_id=revision.id, **cast_call.model_dump()))

    if revision.sunrise is None and revision.sunset is None:
        _fill_computed_sunrise_sunset(db, revision, call_sheet.shoot_date, payload.schedule_items)

    db.commit()
    db.refresh(revision)
    logger.info(
        "Published revision %s for call sheet %s (%d schedule items, %d cast calls)",
        revision.revision_letter,
        call_sheet.id,
        len(payload.schedule_items),
        len(payload.cast_calls),
    )
    return revision


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
    db.refresh(call_sheet)
    return call_sheet


class HeadOfDayNotOnProduction(ValueError):
    """The head of day must be a crew member of this production."""


class CrewCallNotOnProduction(ValueError):
    """A personal call names a crew member of another production (or none)."""


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
    entry = None
    if revision is not None:
        entry = next((e for e in revision.crew_calls if e.crew_member_id == member.id), None)
    return PersonalSheet(
        name=member.contact.name,
        department=member.department,
        position=member.position,
        personal_call=(entry.call_time if entry and entry.call_time else None) or member.standard_call_time or general,
        pickup_time=entry.pickup_time if entry else None,
        note=entry.note if entry else None,
        department_head=head_card,
    )


def previous_revision(call_sheet: CallSheet) -> CallSheetRevision | None:
    """The revision the current one replaced (letters are sequential), or None for a sheet with only REV A."""
    current = call_sheet.current_revision
    if current is None:
        return None
    wanted = chr(ord(current.revision_letter) - 1)
    return next((r for r in call_sheet.revisions if r.revision_letter == wanted), None)


def _scene_order(revision: CallSheetRevision) -> str:
    return ", ".join(item.scene_number for item in sorted(revision.schedule_items, key=lambda i: i.order_index))


def _personal_calls_key(revision: CallSheetRevision) -> dict[uuid.UUID, tuple[str | None, str | None, str | None]]:
    return {e.crew_member_id: (e.call_time, e.pickup_time, e.note) for e in revision.crew_calls}


def revision_changes(before: CallSheetRevision | None, after: CallSheetRevision) -> list[RevisionChange]:
    """What a crew member who read `before` last night needs to know about `after` (FR-23).

    Compares the things that change a person's morning: the two call times,
    the scene order, safety notes, and how many personal calls moved. Fields
    that did not change are left out, so an unchanged sheet yields [] and the
    viewer shows no diff line at all — never an empty "replaces" sentence.
    """
    if before is None:
        return []
    changes: list[RevisionChange] = []
    for field, label, attr in (("crew_call", "Crew call", "general_crew_call"), ("shooting_call", "Shooting call", "shooting_call")):
        old, new = getattr(before, attr), getattr(after, attr)
        if (old or None) != (new or None):
            changes.append(RevisionChange(field=field, label=label, before=old, after=new))
    old_order, new_order = _scene_order(before), _scene_order(after)
    if old_order != new_order:
        changes.append(RevisionChange(field="scene_order", label="Scenes", before=old_order or None, after=new_order or None))
    if (before.safety_notes or None) != (after.safety_notes or None):
        changes.append(RevisionChange(field="safety_notes", label="Safety", before=before.safety_notes, after=after.safety_notes))
    old_pc, new_pc = _personal_calls_key(before), _personal_calls_key(after)
    moved = sum(1 for k in set(old_pc) | set(new_pc) if old_pc.get(k) != new_pc.get(k))
    if moved:
        changes.append(RevisionChange(field="personal_calls", label="Personal calls", before=None, after=f"{moved} changed"))
    return changes


def change_summary(changes: list[RevisionChange]) -> str:
    """One line for a push notification: the first two changes, "before → after"."""
    parts = []
    for c in changes[:2]:
        if c.field == "personal_calls":
            parts.append(f"{c.label.lower()} {c.after}")
        else:
            parts.append(f"{c.label.lower()} {c.before or '—'} → {c.after or '—'}")
    return "; ".join(parts) if parts else "no changes to calls or scenes"


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
    days = [
        CrewDayRef(call_sheet_id=s.id, shoot_date=s.shoot_date, day_number=s.day_number, day_count=s.day_count, unit_name=s.unit_name,
                   revision_letter=s.current_revision.revision_letter if s.current_revision else None)
        for s in sheets
    ]
    upcoming = [d for d in days if d.shoot_date >= today]
    chosen = upcoming[0] if upcoming else (days[-1] if days else None)
    return CrewNextDay(production_name=member.production.name, crew_member_name=member.contact.name,
                       call_sheet_id=chosen.call_sheet_id if chosen else None, days=days)

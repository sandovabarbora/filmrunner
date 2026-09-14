"""Business logic for publishing call-sheet revisions.

Kept separate from the router (I/O layer) per the "separate business logic
from I/O" standard — this module has no FastAPI imports and is unit-testable
without spinning up the HTTP layer.

Reference: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
"""

import logging
import string

from sqlalchemy.orm import Session

from app.models.production import CrewMember
from app.models.call_sheet import CallSheet, CallSheetRevision, CastCallEntry, ScheduleItem
from app.schemas.call_sheet import CallSheetContacts, ContactCard, CallSheetCreate, CallSheetRevisionCreate

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
    for cast_call in payload.cast_calls:
        db.add(CastCallEntry(revision_id=revision.id, **cast_call.model_dump()))

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

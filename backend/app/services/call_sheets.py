"""Business logic for publishing call-sheet revisions.

Kept separate from the router (I/O layer) per the "separate business logic
from I/O" standard — this module has no FastAPI imports and is unit-testable
without spinning up the HTTP layer.

Reference: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
"""

import logging
import string

from sqlalchemy.orm import Session

from app.models.call_sheet import CallSheet, CallSheetRevision, CastCallEntry, ScheduleItem
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate

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
    db: Session, call_sheet: CallSheet, payload: CallSheetRevisionCreate
) -> CallSheetRevision:
    """Create a new revision on an existing call sheet, marking prior
    revisions as no longer current.

    This is the "hot revision" operation: same-day corrections happen by
    adding a new immutable revision, never by editing an existing one — see
    DESIGN.md for why.
    """
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
        created_by=payload.created_by,
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


def create_call_sheet(db: Session, production_id, payload: CallSheetCreate) -> CallSheet:
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

    publish_revision(db, call_sheet, payload.initial_revision)
    db.refresh(call_sheet)
    return call_sheet

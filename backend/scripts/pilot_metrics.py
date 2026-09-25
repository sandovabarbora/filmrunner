"""The pilot's numbers per shoot day (FR-96, docs/pilot/pilot-plan.md).

Read-only: opens the configured database with the app's own SessionLocal and
only ever SELECTs, like retention_report.py. Reads the FR-36 read receipts
(`revision_views`), so it counts only personal links loaded live — the shared
crew link and cached reloads are invisible, which makes every share a lower bound.

Usage:
    cd backend && python -m scripts.pilot_metrics <production_id>
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus, CrewCallEntry
from app.models.production import CrewMember, Production
from app.models.seen import RevisionView

PRAGUE = ZoneInfo("Europe/Prague")
FAST = timedelta(minutes=30)


@dataclass
class RevisionOpens:
    letter: str
    opened_fast: int  # first opened within FAST of publishing
    crew: int


@dataclass
class DayMetrics:
    day_number: int
    shoot_date: date
    status: str
    current_letter: str | None
    crew: int  # crew members with a personal link (every crew member has one)
    with_call: int  # of those, how many have a call time to measure against
    opened_before_call: int
    later_revisions: list[RevisionOpens] = field(default_factory=list)


def call_at(on: date, hhmm: str | None) -> datetime | None:
    """A "06:30" Prague wall-clock call as naive UTC, the way `now()` stores timestamps here."""
    try:
        hours, minutes = (int(part) for part in (hhmm or "").strip().split(":")[:2])
        local = datetime.combine(on, time(hours, minutes), tzinfo=PRAGUE)
    except ValueError:
        return None
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def day_metrics(db: Session, production_id: uuid.UUID) -> list[DayMetrics]:
    crew = db.scalars(select(CrewMember).where(CrewMember.production_id == production_id)).all()
    sheets = db.scalars(
        select(CallSheet)
        .where(CallSheet.production_id == production_id, CallSheet.status != CallSheetStatus.DRAFT)
        .order_by(CallSheet.shoot_date, CallSheet.day_number)
    ).all()

    days = []
    for sheet in sheets:
        current = sheet.current_revision
        day = DayMetrics(sheet.day_number, sheet.shoot_date, sheet.status.value, current.revision_letter if current else None, len(crew), 0, 0)
        if current:
            seen = _first_seen(db, current.id)
            own_calls = {e.crew_member_id: e.call_time for e in db.scalars(select(CrewCallEntry).where(CrewCallEntry.revision_id == current.id))}
            for member in crew:
                # Same precedence as the personal sheet (services/call_sheets.py): own call, standing time, general call.
                call = call_at(sheet.shoot_date, own_calls.get(member.id) or member.standard_call_time or current.general_crew_call)
                if call is None:
                    continue
                day.with_call += 1
                if member.id in seen and seen[member.id] < call:
                    day.opened_before_call += 1
        for revision in sorted(sheet.revisions, key=lambda r: r.revision_letter):
            if revision.revision_letter == "A":
                continue
            seen = _first_seen(db, revision.id)
            fast = sum(1 for member in crew if member.id in seen and seen[member.id] - revision.created_at <= FAST)
            day.later_revisions.append(RevisionOpens(revision.revision_letter, fast, len(crew)))
        days.append(day)
    return days


def _first_seen(db: Session, revision_id: uuid.UUID) -> dict[uuid.UUID, datetime]:
    rows = db.execute(select(RevisionView.crew_member_id, RevisionView.first_seen_at).where(RevisionView.revision_id == revision_id))
    return {member_id: first_seen for member_id, first_seen in rows}


def _share(part: int, whole: int) -> str:
    return f"{part} / {whole} ({round(100 * part / whole)} %)"


def report(days: list[DayMetrics]) -> str:
    if not days:
        return "no published days yet"
    lines = []
    for d in days:
        lines.append(f"Day {d.day_number} · {d.shoot_date.isoformat()} · REV {d.current_letter or '-'} · {d.status}")
        if d.crew == 0 or d.with_call == 0:
            lines.append("  opened before own call: no data (no crew with a personal link and a call time)")
        else:
            skipped = d.crew - d.with_call
            lines.append(f"  opened before own call: {_share(d.opened_before_call, d.with_call)}" + (f"  [{skipped} without a call time, not counted]" if skipped else ""))
        if not d.later_revisions:
            lines.append("  later revisions: none (REV A only)")
        for r in d.later_revisions:
            lines.append(f"  REV {r.letter} opened within 30 min: " + (_share(r.opened_fast, r.crew) if r.crew else "no data"))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        production_id = uuid.UUID(argv[0])
    except ValueError:
        print(f"not a production id: {argv[0]!r}", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        production = db.get(Production, production_id)
        if production is None:
            print(f"no production {production_id}", file=sys.stderr)
            return 1
        print(f"{production.name} — personal-link opens only, so a lower bound (docs/pilot/pilot-plan.md)\n")
        print(report(day_metrics(db, production_id)))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

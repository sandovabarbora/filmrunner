"""How many stored times the FR-222 validation would refuse, so they can be fixed before the pilot.

A time field took free text until FR-222. A stored value such as "abc" still
reads back, but the editor sends it again on an unrelated save and the API now
refuses it. This counts those rows per column. It prints ids only: a time can
sit next to a name, and the ids are enough to open the day or the person.

Read-only: the transaction is set READ ONLY, so the database refuses any write.

Usage:
    cd backend && python -m scripts.time_format_report
"""

from __future__ import annotations

from sqlalchemy import Column, select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.call_sheet import CallSheet, CallSheetRevision, CastCallEntry, CrewCallEntry
from app.models.production import CastMember, CrewMember
from app.schemas.fields import _clock_time

TIME_COLUMNS: list[Column] = [
    CallSheetRevision.__table__.c.general_crew_call, CallSheetRevision.__table__.c.shooting_call,
    CallSheetRevision.__table__.c.sunrise, CallSheetRevision.__table__.c.sunset,
    CrewCallEntry.__table__.c.call_time, CrewCallEntry.__table__.c.pickup_time,
    CastCallEntry.__table__.c.pickup_time, CastCallEntry.__table__.c.call_time,
    CastCallEntry.__table__.c.makeup_hair_time, CastCallEntry.__table__.c.on_set_time,
    CrewMember.__table__.c.standard_call_time, CastMember.__table__.c.standard_pickup_time,
    CallSheet.__table__.c.actual_first_shot, CallSheet.__table__.c.actual_lunch_out,
    CallSheet.__table__.c.actual_lunch_in, CallSheet.__table__.c.actual_wrap,
]


def _refused(value: str) -> bool:
    try:
        _clock_time(value)
    except ValueError:
        return True
    return False


def refused_ids(db: Session) -> dict[str, list[str]]:
    """Ids per "table.column" whose stored value the validation would refuse."""
    report: dict[str, list[str]] = {}
    for column in TIME_COLUMNS:
        rows = db.execute(select(column.table.c.id, column).where(column.is_not(None))).all()
        report[f"{column.table.name}.{column.name}"] = [str(row_id) for row_id, value in rows if _refused(value)]
    return report


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        report = refused_ids(db)
    finally:
        db.rollback()
        db.close()
    print(f"Stored times the API would now refuse: {sum(len(ids) for ids in report.values())}")
    for name, ids in report.items():
        print(f"  {name}: {len(ids)}")
        for row_id in ids:
            print(f"    {row_id}")


if __name__ == "__main__":
    main()

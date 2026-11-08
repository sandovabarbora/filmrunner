"""FR-222 review: the founder's read-only count of stored times the validation would refuse."""

from datetime import date

from sqlalchemy import Enum, String

from app.database import Base
from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus
from app.models.production import Production
from scripts.time_format_report import TIME_COLUMNS, refused_ids


def test_it_covers_every_time_column() -> None:
    """Every String(10) column holds a time; a new one has to be added to the report."""
    time_like = {f"{t.name}.{c.name}" for t in Base.metadata.tables.values() for c in t.columns
                 if isinstance(c.type, String) and not isinstance(c.type, Enum) and c.type.length == 10}
    assert time_like == {f"{c.table.name}.{c.name}" for c in TIME_COLUMNS}


def test_it_counts_what_would_be_refused_and_nothing_else(db_session) -> None:
    production = Production(name="Times")
    db_session.add(production)
    db_session.flush()
    sheet = CallSheet(production_id=production.id, shoot_date=date(2031, 1, 1), day_number=1, day_count=1, status=CallSheetStatus.PUBLISHED, actual_wrap="pozdě")
    db_session.add(sheet)
    db_session.flush()
    bad = CallSheetRevision(call_sheet_id=sheet.id, revision_letter="A", is_current=False, general_crew_call="25:99", sunrise="6,30")
    good = CallSheetRevision(call_sheet_id=sheet.id, revision_letter="B", is_current=True, general_crew_call="6.30", sunrise="")
    db_session.add_all([bad, good])
    db_session.commit()

    report = refused_ids(db_session)
    assert str(bad.id) in report["call_sheet_revisions.general_crew_call"]
    assert str(good.id) not in report["call_sheet_revisions.general_crew_call"]
    assert str(bad.id) not in report["call_sheet_revisions.sunrise"]
    assert str(sheet.id) in report["call_sheets.actual_wrap"]

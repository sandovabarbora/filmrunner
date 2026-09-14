"""Tests for the demo seed script (FR-8): it must produce a real,
publishable call sheet and never duplicate it on a second run — a deploy
or a routine could plausibly run it more than once against the same
database.
"""

import uuid

from app.database import SessionLocal
from app.models.call_sheet import CallSheet
from app.models.production import Location, Production
from app.seed_demo import DEMO_PRODUCTION_NAME, seed


def _cleanup(production_id):
    """Remove the seeded rows so this test doesn't leak state into others
    (seed() commits on its own connection, outside the db_session
    savepoint other tests roll back)."""
    db = SessionLocal()
    try:
        for call_sheet in db.query(CallSheet).filter(CallSheet.production_id == production_id):
            for revision in call_sheet.revisions:
                for item in list(revision.schedule_items):
                    db.delete(item)
                db.delete(revision)
            db.delete(call_sheet)
        for location in db.query(Location).filter(Location.production_id == production_id):
            db.delete(location)
        db.flush()  # children must be gone before the production row is deleted
        db.query(Production).filter(Production.id == production_id).delete()
        db.commit()
    finally:
        db.close()


class TestSeedDemo:
    def test_seed_creates_a_real_publishable_call_sheet(self):
        call_sheet_id = seed()
        db = SessionLocal()
        try:
            call_sheet = db.get(CallSheet, uuid.UUID(call_sheet_id))
            assert call_sheet is not None
            assert call_sheet.production.name == DEMO_PRODUCTION_NAME
            assert call_sheet.current_revision is not None
            assert call_sheet.current_revision.revision_letter == "A"
            assert len(call_sheet.current_revision.schedule_items) == 2
            production_id = call_sheet.production_id
        finally:
            db.close()
        _cleanup(production_id)

    def test_seed_is_idempotent(self):
        first_id = seed()
        second_id = seed()
        assert first_id == second_id

        db = SessionLocal()
        try:
            production = (
                db.query(Production).filter(Production.name == DEMO_PRODUCTION_NAME).first()
            )
            production_id = production.id
        finally:
            db.close()
        _cleanup(production_id)

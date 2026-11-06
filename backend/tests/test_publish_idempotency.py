"""FR-142: a double-tap (or a flaky-connection retry) publishing the same
call sheet revision twice in quick succession must collapse into exactly
one new revision and exactly one push attempt per subscriber, not two.

Uses two genuinely independent, real sessions/connections racing against
each other in two threads — the shared, savepoint-wrapped `db_session`
fixture every other test in this suite uses pins all of a test's work to
one connection, which can never race against itself the way two
overlapping requests from a flaky client actually would.
"""

import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models.call_sheet import CallSheet
from app.models.production import Contact, CrewMember, Production
from app.models.push import PushSubscription
from app.schemas.call_sheet import CallSheetRevisionCreate
from app.services import push as push_service
from app.services.call_sheets import create_call_sheet, publish_revision
from app.services.notifications import notify_subscribers

from .test_call_sheets import _minimal_call_sheet_payload


@pytest.fixture()
def vapid_configured():
    """Simulate the founder having set the two Fly secrets (INBOX #5), the
    same way tests/test_push.py does, so a push is actually attempted
    rather than silently skipped as "not configured"."""
    from app.config import get_settings

    settings = get_settings()
    original = (settings.vapid_public_key, settings.vapid_private_key)
    settings.vapid_public_key = "test-public-key"
    settings.vapid_private_key = push_service.generate_keypair()[1]
    yield settings
    settings.vapid_public_key, settings.vapid_private_key = original


@pytest.fixture()
def real_call_sheet(vapid_configured):
    """A committed-for-real production, one subscribed crew member, and a
    published REV A — set up (and torn down) outside the suite's usual
    rolled-back `db_session`, because the test itself needs two other real
    connections to be able to see this data mid-test."""
    db = SessionLocal()
    production = Production(name="FR-142 double-tap test")
    db.add(production)
    db.flush()
    contact = Contact(name="Double Tap Test Crew")
    db.add(contact)
    db.flush()
    crew_member = CrewMember(production_id=production.id, contact_id=contact.id, department="Grip", position="Key grip")
    db.add(crew_member)
    db.flush()
    db.add(
        PushSubscription(
            crew_member_id=crew_member.id,
            endpoint=f"https://fcm.googleapis.com/fcm/send/fr-142-{uuid.uuid4()}",
            p256dh="BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA",
            auth="fake-auth-key",
            link_url="https://filmrunner.example/?sheet=abc",
        )
    )
    call_sheet = create_call_sheet(db, production.id, _minimal_call_sheet_payload())
    db.commit()
    call_sheet_id = call_sheet.id
    production_id = production.id
    crew_member_id = crew_member.id
    contact_id = contact.id
    db.close()

    try:
        yield call_sheet_id
    finally:
        cleanup = SessionLocal()
        try:
            sheet = cleanup.get(CallSheet, call_sheet_id)
            for revision in list(sheet.revisions):
                children = (
                    list(revision.schedule_items)
                    + list(revision.cast_calls)
                    + list(revision.crew_calls)
                    + list(revision.distribution_log)
                )
                for child in children:
                    cleanup.delete(child)
                cleanup.delete(revision)
            cleanup.delete(sheet)
            cleanup.flush()  # autoflush is off (app/database.py) — the bulk deletes below need these gone first
            cleanup.query(PushSubscription).filter(PushSubscription.crew_member_id == crew_member_id).delete()
            cleanup.query(CrewMember).filter(CrewMember.id == crew_member_id).delete()
            cleanup.query(Contact).filter(Contact.id == contact_id).delete()
            cleanup.query(Production).filter(Production.id == production_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


def test_two_concurrent_publishes_for_the_same_day_yield_one_revision_and_one_push(real_call_sheet):
    call_sheet_id = real_call_sheet
    barrier = threading.Barrier(2)
    results = {}

    def _publish(name: str) -> None:
        db = SessionLocal()
        try:
            call_sheet = db.get(CallSheet, call_sheet_id)
            payload = CallSheetRevisionCreate(general_crew_call="05:30", safety_notes="Double-tap test")
            barrier.wait(timeout=5)
            revision, is_new = publish_revision(db, call_sheet, payload)
            if is_new:
                notify_subscribers(db, call_sheet, revision)
            results[name] = (revision.id, revision.revision_letter, is_new)
        finally:
            db.close()

    with patch("app.services.push.webpush", MagicMock()) as mock_webpush:
        t1 = threading.Thread(target=_publish, args=("first",))
        t2 = threading.Thread(target=_publish, args=("second",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not t1.is_alive() and not t2.is_alive(), "a publish call hung instead of completing"
        assert set(results) == {"first", "second"}

        revision_ids = {r[0] for r in results.values()}
        revision_letters = {r[1] for r in results.values()}
        is_new_flags = sorted(r[2] for r in results.values())

        assert revision_ids == {next(iter(revision_ids))}, "both calls must settle on the same revision, not two"
        assert revision_letters == {"B"}, f"expected exactly one hot revision (B), got {revision_letters}"
        assert is_new_flags == [False, True], "exactly one of the two double-tapped calls must be the real publish"

        assert mock_webpush.call_count == 1, (
            f"expected exactly one push attempt for the one subscriber, got {mock_webpush.call_count}"
        )

    db = SessionLocal()
    try:
        call_sheet = db.get(CallSheet, call_sheet_id)
        assert len(call_sheet.revisions) == 2, "A (initial) + exactly one hot revision, never two"
    finally:
        db.close()


def test_sequential_publishes_are_unaffected_by_the_lock(real_call_sheet):
    """The lock must not turn a normal, non-concurrent publish sequence into
    a duplicate: two real publishes made one after another (no contention)
    still each produce their own distinct revision."""
    call_sheet_id = real_call_sheet
    db = SessionLocal()
    try:
        call_sheet = db.get(CallSheet, call_sheet_id)
        revision_b, is_new_b = publish_revision(db, call_sheet, CallSheetRevisionCreate(general_crew_call="05:30"))
        revision_c, is_new_c = publish_revision(db, call_sheet, CallSheetRevisionCreate(general_crew_call="05:00"))
        db.commit()
        assert is_new_b is True
        assert is_new_c is True
        assert revision_b.revision_letter == "B"
        assert revision_c.revision_letter == "C"
    finally:
        db.close()

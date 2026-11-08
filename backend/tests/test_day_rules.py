"""FR-222: a day cannot move into the past, and the same day cannot exist twice."""

import threading
from datetime import date
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import SessionLocal
from app.models.call_sheet import CallSheet, CallSheetRevision, ScheduleItem
from app.models.production import Location, Production
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate
from app.services import push as push_service
from app.services.call_sheets import DuplicateDay, create_call_sheet_once

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
pytestmark = pytest.mark.usefixtures("background_tasks_share_db")


@pytest.fixture()
def vapid_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", push_service.generate_keypair()[1])


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Rules"}, headers=AUTH).json()["id"]


def _body(**overrides) -> dict:
    return {"shoot_date": "2031-03-03", "day_number": 3, "day_count": 9, "unit_name": "Main Unit",
            "initial_revision": {"general_crew_call": "06:30", "schedule_items": [{"order_index": 1, "scene_number": "42", "int_ext": "INT", "day_night": "DAY", "set_description": "Set", "page_count_eighths": 8}]},
            **overrides}


def _create(client: TestClient, pid: str, **overrides):
    return client.post(f"/api/v1/productions/{pid}/call-sheets", json=_body(**overrides), headers=AUTH)


def _reschedule(client: TestClient, sheet_id: str, to: str, letter: str = "A"):
    return client.post(f"/api/v1/call-sheets/{sheet_id}/reschedule", json={"shoot_date": to, "expected_revision_letter": letter}, headers=AUTH)


# --- moving into the past -----------------------------------------------------------------------

def test_rescheduling_to_a_past_date_is_refused_and_says_why(client: TestClient, prague_clock) -> None:
    prague_clock("2026-11-10T12:00")
    pid = _production(client)
    sheet = _create(client, pid, shoot_date="2026-11-12").json()
    r = _reschedule(client, sheet["id"], "2026-11-09")
    assert r.status_code == 409 and "past" in r.json()["detail"] and "2026-11-09" in r.json()["detail"]
    assert client.get(f"/api/v1/call-sheets/{sheet['id']}", headers=AUTH).json()["shoot_date"] == "2026-11-12"


def test_today_is_prague_today_not_the_servers(client: TestClient, prague_clock) -> None:
    """00:30 on the 10th in Prague is still the 9th in UTC, where the server runs: the 9th is already past."""
    prague_clock("2026-11-10T00:30")
    pid = _production(client)
    sheet = _create(client, pid, shoot_date="2026-11-12").json()
    assert _reschedule(client, sheet["id"], "2026-11-09").status_code == 409
    assert _reschedule(client, sheet["id"], "2026-11-10").status_code == 200


def test_swapping_cannot_move_a_day_into_the_past_either(client: TestClient, prague_clock) -> None:
    prague_clock("2026-11-10T12:00")
    pid = _production(client)
    done = _create(client, pid, shoot_date="2026-11-08", day_number=1).json()
    ahead = _create(client, pid, shoot_date="2026-11-12", day_number=2).json()
    r = client.post(f"/api/v1/call-sheets/{ahead['id']}/swap-with", json={"other_call_sheet_id": done["id"], "expected_revision_letter": "A", "expected_other_revision_letter": "A"}, headers=AUTH)
    assert r.status_code == 409 and "past" in r.json()["detail"]


# --- the same day twice -------------------------------------------------------------------------

def test_the_same_day_with_other_content_is_refused(client: TestClient) -> None:
    pid = _production(client)
    first = _create(client, pid)
    assert first.status_code == 201
    other = _body()
    other["initial_revision"]["general_crew_call"] = "09:00"
    r = client.post(f"/api/v1/productions/{pid}/call-sheets", json=other, headers=AUTH)
    assert r.status_code == 409 and "Day 3" in r.json()["detail"] and "2031-03-03" in r.json()["detail"]
    assert len(client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json()) == 1


def test_a_retry_with_the_same_payload_returns_the_day_and_tells_nobody_again(client: TestClient, vapid_configured) -> None:
    pid = _production(client)
    contact = client.post("/api/v1/contacts", json={"name": "Jana"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "Camera", "position": "AC"}, headers=AUTH).json()
    subscribed = client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription",
                             json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"}, "link_url": "https://x/?me=t"})
    assert subscribed.status_code < 300, subscribed.text
    with patch("app.services.push.webpush") as webpush:
        first = _create(client, pid)
        retry = _create(client, pid)
    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json()["id"] == first.json()["id"] and retry.json()["current_revision"]["revision_letter"] == "A"
    assert webpush.call_count == 1
    assert len(client.get(f"/api/v1/call-sheets/{first.json()['id']}/history", headers=AUTH).json()) == 1


def test_a_retry_still_matches_when_the_server_filled_sun_and_weather(client: TestClient, db_session) -> None:
    pid = _production(client)
    location = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Praha"}, headers=AUTH).json()["id"]
    db_session.query(Location).filter(Location.id == location).update({"geo_lat": 50.0755, "geo_lng": 14.4378})
    db_session.commit()
    body = _body()
    body["initial_revision"]["schedule_items"][0]["location_id"] = location
    first = client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH)
    assert first.json()["current_revision"]["sunrise"] is not None
    assert client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH).status_code == 200


def test_a_retry_after_a_newer_revision_still_returns_the_day(client: TestClient) -> None:
    """An offline phone resending its create must not fail, and must not undo what was published since."""
    pid = _production(client)
    first = _create(client, pid).json()
    client.post(f"/api/v1/call-sheets/{first['id']}/revisions", json={"general_crew_call": "07:00"}, headers=AUTH)
    retry = _create(client, pid)
    assert retry.status_code == 200 and retry.json()["current_revision"]["revision_letter"] == "B"
    assert retry.json()["current_revision"]["general_crew_call"] == "07:00"


def test_a_retried_draft_stays_a_draft(client: TestClient) -> None:
    pid = _production(client)
    first = _create(client, pid, draft=True)
    retry = _create(client, pid, draft=True)
    assert (first.status_code, retry.status_code) == (201, 200) and retry.json()["status"] == "draft"


def test_asking_to_publish_over_an_existing_draft_is_not_a_retry(client: TestClient) -> None:
    pid = _production(client)
    _create(client, pid, draft=True)
    assert _create(client, pid).status_code == 409


@pytest.mark.parametrize("overrides", [{"day_number": 4}, {"unit_name": "Second Unit"}, {"shoot_date": "2031-03-04"}])
def test_a_different_date_number_or_unit_is_a_different_day(client: TestClient, overrides) -> None:
    pid = _production(client)
    assert _create(client, pid).status_code == 201
    assert _create(client, pid, **overrides).status_code == 201


def test_two_productions_do_not_collide(client: TestClient) -> None:
    assert _create(client, _production(client)).status_code == 201
    assert _create(client, _production(client)).status_code == 201


def test_a_cancelled_day_can_be_replaced_and_then_cannot_come_back_on_top_of_it(client: TestClient) -> None:
    pid = _production(client)
    cancelled = _create(client, pid).json()
    client.post(f"/api/v1/call-sheets/{cancelled['id']}/cancel", headers=AUTH)
    replacement = _create(client, pid)
    assert replacement.status_code == 201 and replacement.json()["id"] != cancelled["id"]
    r = client.post(f"/api/v1/call-sheets/{cancelled['id']}/restore", headers=AUTH)
    assert r.status_code == 409 and "Day 3" in r.json()["detail"]
    assert client.get(f"/api/v1/call-sheets/{cancelled['id']}", headers=AUTH).json()["status"] == "cancelled"


def test_two_creates_at_once_make_one_day() -> None:
    """Real sessions: without a lock both would look, find nothing, and insert."""
    setup = SessionLocal()
    production = Production(name=f"Race {uuid.uuid4()}")
    setup.add(production)
    setup.commit()
    production_id = production.id
    setup.close()

    payload = CallSheetCreate(shoot_date="2031-03-03", day_number=3, day_count=9, initial_revision=CallSheetRevisionCreate(general_crew_call="06:30"))
    barrier = threading.Barrier(2)
    outcomes: list = []

    def create() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            sheet, is_new = create_call_sheet_once(db, production_id, payload)
            outcomes.append((sheet.id, is_new))
        except DuplicateDay as exc:
            outcomes.append(exc)
        finally:
            db.close()

    threads = [threading.Thread(target=create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    cleanup = SessionLocal()
    try:
        sheets = cleanup.query(CallSheet).filter(CallSheet.production_id == production_id).all()
        assert len(sheets) == 1
        assert sorted(is_new for _, is_new in outcomes) == [False, True]
        assert len({sheet_id for sheet_id, _ in outcomes}) == 1
    finally:
        for sheet in cleanup.query(CallSheet).filter(CallSheet.production_id == production_id).all():
            for revision in list(sheet.revisions):
                cleanup.query(ScheduleItem).filter(ScheduleItem.revision_id == revision.id).delete()
                cleanup.query(CallSheetRevision).filter(CallSheetRevision.id == revision.id).delete()
            cleanup.delete(sheet)
        cleanup.flush()
        cleanup.query(Production).filter(Production.id == production_id).delete()
        cleanup.commit()
        cleanup.close()


# --- FR-222 review: restore and reschedule wait for a create of the same day. ----------------------

def _race_against_a_create(change, elsewhere_number: int = 3) -> tuple[object, int]:
    """A create of Day 3 of the Main Unit on 2031-03-03 is under way and not committed while `change` runs in another session.
    Besides it: a cancelled Day 3 on that date, Day `elsewhere_number` on 2031-03-10, and a Second Unit Day 3 on 2031-03-03.
    Returns what the change did, and how many live Main Unit days exist on 2031-03-03 afterwards."""
    from datetime import date as day

    from sqlalchemy import text as sql

    from app.models.call_sheet import CallSheetStatus
    from app.services.replan import ReplanConflict

    setup = SessionLocal()
    production = Production(name=f"Race {uuid.uuid4()}")
    setup.add(production)
    setup.flush()
    cancelled = CallSheet(production_id=production.id, shoot_date=day(2031, 3, 3), day_number=3, day_count=9, unit_name="Main Unit", status=CallSheetStatus.CANCELLED)
    elsewhere = CallSheet(production_id=production.id, shoot_date=day(2031, 3, 10), day_number=elsewhere_number, day_count=9, unit_name="Main Unit", status=CallSheetStatus.PUBLISHED)
    second_unit = CallSheet(production_id=production.id, shoot_date=day(2031, 3, 3), day_number=3, day_count=9, unit_name="Second Unit", status=CallSheetStatus.PUBLISHED)
    setup.add_all([cancelled, elsewhere, second_unit])
    setup.flush()
    for sheet in (cancelled, elsewhere, second_unit):
        setup.add(CallSheetRevision(call_sheet_id=sheet.id, revision_letter="A", is_current=True, general_crew_call="06:30", shoot_date=sheet.shoot_date))
    setup.commit()
    ids = {"production": production.id, "cancelled": cancelled.id, "elsewhere": elsewhere.id, "second_unit": second_unit.id}
    setup.close()

    creator = SessionLocal()
    creator.execute(sql("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": f"create-day:{ids['production']}:2031-03-03:Main Unit"})
    creator.add(CallSheet(production_id=ids["production"], shoot_date=day(2031, 3, 3), day_number=3, day_count=9, unit_name="Main Unit", status=CallSheetStatus.PUBLISHED))
    creator.flush()
    outcome: dict = {}

    def run() -> None:
        db = SessionLocal()
        try:
            outcome["result"] = change(db, ids)
        except ReplanConflict as exc:
            db.rollback()
            outcome["result"] = exc
        finally:
            db.close()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(0.5)
    waited = thread.is_alive()
    creator.commit()
    creator.close()
    thread.join(10)

    check = SessionLocal()
    try:
        live = check.query(CallSheet).filter(CallSheet.production_id == ids["production"], CallSheet.shoot_date == day(2031, 3, 3),
                                             CallSheet.unit_name == "Main Unit", CallSheet.status != CallSheetStatus.CANCELLED).count()
    finally:
        for sheet in check.query(CallSheet).filter(CallSheet.production_id == ids["production"]).all():
            for revision in list(sheet.revisions):
                check.query(ScheduleItem).filter(ScheduleItem.revision_id == revision.id).delete()
                check.query(CallSheetRevision).filter(CallSheetRevision.id == revision.id).delete()
            check.delete(sheet)
        check.flush()
        check.query(Production).filter(Production.id == ids["production"]).delete()
        check.commit()
        check.close()
    assert waited, "the change did not wait for the create holding the same day's lock"
    return outcome["result"], live


def test_restoring_waits_for_a_create_of_the_same_day_and_then_refuses() -> None:
    from app.services.replan import ReplanConflict, restore_day

    result, live = _race_against_a_create(lambda db, ids: restore_day(db, db.get(CallSheet, ids["cancelled"])))
    assert isinstance(result, ReplanConflict) and live == 1


def test_rescheduling_waits_for_a_create_on_the_target_date_and_then_refuses(prague_clock) -> None:
    from app.services.replan import ReplanConflict, reschedule_day

    prague_clock("2031-01-01T12:00")
    result, live = _race_against_a_create(lambda db, ids: reschedule_day(db, db.get(CallSheet, ids["elsewhere"]), date(2031, 3, 3), "A", "ad"))
    assert isinstance(result, ReplanConflict) and live == 1


def test_rescheduling_another_day_number_onto_the_date_waits_too(prague_clock) -> None:
    """The clash rule is one Main Unit day per date, whatever its number, so the lock has to be by date too."""
    from app.services.replan import ReplanConflict, reschedule_day

    prague_clock("2031-01-01T12:00")
    result, live = _race_against_a_create(lambda db, ids: reschedule_day(db, db.get(CallSheet, ids["elsewhere"]), date(2031, 3, 3), "A", "ad"), elsewhere_number=5)
    assert isinstance(result, ReplanConflict) and live == 1


def test_swapping_waits_for_a_create_on_the_slot_it_lands_on(prague_clock) -> None:
    """Day 5 of the Main Unit swaps with the Second Unit's day on 2031-03-03, so it lands on the slot being created."""
    from app.services.replan import swap_days

    prague_clock("2031-01-01T12:00")
    _race_against_a_create(lambda db, ids: swap_days(db, db.get(CallSheet, ids["elsewhere"]), db.get(CallSheet, ids["second_unit"]), "A", "A", "ad"), elsewhere_number=5)

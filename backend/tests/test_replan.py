"""FR-203: moving a scene or a day is one action, and both sheets say what happened."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import push as push_service
from app.services import replan

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
pytestmark = pytest.mark.usefixtures("background_tasks_share_db")


@pytest.fixture(autouse=True)
def _before_the_dates_used_here(prague_clock) -> None:
    # These tests name dates in November 2026; rescheduling onto a past date is refused, and they would start failing then.
    prague_clock("2026-11-01T12:00")


def _scene(n: str, order: int, description: str = "Set") -> dict:
    return {"order_index": order, "scene_number": n, "int_ext": "INT", "day_night": "DAY", "set_description": description, "page_count_eighths": 8}


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Replan"}, headers=AUTH).json()["id"]


def _day(client: TestClient, pid: str, number: int, date: str, scenes: list[dict], **extra) -> dict:
    body = {"shoot_date": date, "day_number": number, "day_count": 24, "initial_revision": {"general_crew_call": "07:00", "schedule_items": scenes}, **extra}
    r = client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def _read(client: TestClient, sheet: dict) -> dict:
    return client.get(f"/api/v1/call-sheets/{sheet['id']}", headers=AUTH).json()


def _move(client: TestClient, source: dict, target: dict, scene: str, letter="A", target_letter="A", occurrence=0):
    return client.post(f"/api/v1/call-sheets/{source['id']}/move-scene", json={
        "scene_number": scene, "occurrence": occurrence, "target_call_sheet_id": target["id"],
        "expected_revision_letter": letter, "expected_target_revision_letter": target_letter,
    }, headers=AUTH)


def _scenes(read: dict) -> list[str]:
    return [i["scene_number"] for i in sorted(read["current_revision"]["schedule_items"], key=lambda i: i["order_index"])]


def test_moving_a_scene_publishes_both_days_and_each_points_at_the_other(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1, "River"), _scene("43", 2)])
    d8 = _day(client, pid, 8, "2026-11-11", [_scene("17", 1)])
    assert _move(client, d7, d8, "42").status_code == 200

    source, target = _read(client, d7), _read(client, d8)
    assert (_scenes(source), source["current_revision"]["revision_letter"]) == (["43"], "B")
    assert (_scenes(target), target["current_revision"]["revision_letter"]) == (["17", "42"], "B")
    arrived = next(i for i in target["current_revision"]["schedule_items"] if i["scene_number"] == "42")
    assert arrived["set_description"] == "River"

    out = source["changes"]
    assert [c["field"] for c in out] == ["scene_moved_out"]
    assert (out[0]["label"], out[0]["after"]) == ("Scene 42 moved to", "Day 8, 2026-11-11")
    assert (out[0]["other_call_sheet_id"], out[0]["other_day_number"]) == (d8["id"], 8)
    assert [(c["field"], c["other_call_sheet_id"], c["scenes"]) for c in target["changes"]] == [("scene_moved_in", d7["id"], ["42"])]


def test_the_failure_of_either_day_leaves_both_untouched(client: TestClient, monkeypatch) -> None:
    """Failure case: a scene must never end up on neither day or on both."""
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    d8 = _day(client, pid, 8, "2026-11-11", [])
    real = replan.publish_revision
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("26 revisions")
        return real(*args, **kwargs)

    monkeypatch.setattr(replan, "publish_revision", fail_on_second)
    assert _move(client, d7, d8, "42").status_code == 409
    assert (_scenes(_read(client, d7)), _scenes(_read(client, d8))) == (["42"], [])
    assert (_read(client, d7)["current_revision"]["revision_letter"], _read(client, d8)["current_revision"]["revision_letter"]) == ("A", "A")


def test_a_change_from_a_stale_screen_is_refused(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    d8 = _day(client, pid, 8, "2026-11-11", [])
    client.post(f"/api/v1/call-sheets/{d8['id']}/revisions", json={"general_crew_call": "06:00", "schedule_items": []}, headers=AUTH)
    r = _move(client, d7, d8, "42")
    assert r.status_code == 409 and "REV B" in r.json()["detail"]
    assert _scenes(_read(client, d7)) == ["42"]


def test_the_right_part_of_a_scene_shot_twice_moves(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("7", 1, "Part one"), _scene("7", 2, "Part two")])
    d8 = _day(client, pid, 8, "2026-11-11", [])
    assert _move(client, d7, d8, "7", occurrence=1).status_code == 200
    assert [i["set_description"] for i in _read(client, d7)["current_revision"]["schedule_items"]] == ["Part one"]
    assert [i["set_description"] for i in _read(client, d8)["current_revision"]["schedule_items"]] == ["Part two"]


@pytest.mark.parametrize("scene,expected", [("99", "not on Day 7")])
def test_a_scene_that_is_not_there_is_refused(client: TestClient, scene: str, expected: str) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    d8 = _day(client, pid, 8, "2026-11-11", [])
    r = _move(client, d7, d8, scene)
    assert r.status_code == 409 and expected in r.json()["detail"]


def test_a_planned_day_stays_invisible_when_a_scene_moves_onto_it(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    planned = _day(client, pid, 8, "2026-11-11", [], draft=True)
    assert _move(client, d7, planned, "42").status_code == 200
    read = _read(client, planned)
    assert read["status"] == "draft" and _scenes(read) == ["42"] and read["current_revision"]["revision_letter"] == "A"
    assert client.get(f"/api/v1/public/call-sheets/{planned['id']}").status_code == 404


def test_moving_a_scene_between_productions_is_refused(client: TestClient) -> None:
    d7 = _day(client, _production(client), 7, "2026-11-10", [_scene("42", 1)])
    elsewhere = _day(client, _production(client), 8, "2026-11-11", [])
    assert _move(client, d7, elsewhere, "42").status_code == 409


def test_a_cancelled_day_cannot_be_replanned(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    d8 = _day(client, pid, 8, "2026-11-11", [])
    client.post(f"/api/v1/call-sheets/{d8['id']}/cancel", headers=AUTH)
    r = _move(client, d7, d8, "42")
    assert r.status_code == 409 and "cancelled" in r.json()["detail"]


def test_rescheduling_a_day_is_a_revision_that_names_both_dates(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    r = client.post(f"/api/v1/call-sheets/{d7['id']}/reschedule", json={"shoot_date": "2026-11-12", "expected_revision_letter": "A"}, headers=AUTH)
    assert r.status_code == 200, r.text
    read = r.json()
    assert read["shoot_date"] == "2026-11-12" and read["current_revision"]["revision_letter"] == "B"
    assert _scenes(read) == ["42"]
    assert [(c["field"], c["before"], c["after"]) for c in read["changes"]] == [("shoot_date", "2026-11-10", "2026-11-12")]


def test_rescheduling_onto_a_taken_date_points_at_swapping(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [])
    _day(client, pid, 8, "2026-11-11", [])
    r = client.post(f"/api/v1/call-sheets/{d7['id']}/reschedule", json={"shoot_date": "2026-11-11", "expected_revision_letter": "A"}, headers=AUTH)
    assert r.status_code == 409 and "swap" in r.json()["detail"]
    assert _read(client, d7)["shoot_date"] == "2026-11-10"


def test_swapping_trades_date_and_number_and_keeps_the_scenes(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    d8 = _day(client, pid, 8, "2026-11-11", [_scene("17", 1)])
    r = client.post(f"/api/v1/call-sheets/{d7['id']}/swap-with", json={"other_call_sheet_id": d8["id"], "expected_revision_letter": "A", "expected_other_revision_letter": "A"}, headers=AUTH)
    assert r.status_code == 200, r.text
    a, b = _read(client, d7), _read(client, d8)
    assert (a["shoot_date"], a["day_number"], _scenes(a)) == ("2026-11-11", 8, ["42"])
    assert (b["shoot_date"], b["day_number"], _scenes(b)) == ("2026-11-10", 7, ["17"])
    assert [(c["before"], c["after"]) for c in a["changes"] if c["field"] == "shoot_date"] == [("2026-11-10", "2026-11-11")]


def test_both_days_are_pushed_when_a_scene_moves(client: TestClient, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", push_service.generate_keypair()[1])
    pid = _production(client)
    contact = client.post("/api/v1/contacts", json={"name": "Jana"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "Grip", "position": "Key grip"}, headers=AUTH).json()
    client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json={
        "endpoint": "https://fcm.googleapis.com/fcm/send/a", "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake"}, "link_url": "https://example.com/x",
    })
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1)])
    d8 = _day(client, pid, 8, "2026-11-11", [])
    with patch.object(push_service, "webpush") as mocked:
        assert _move(client, d7, d8, "42").status_code == 200
    bodies = [c.kwargs["data"] for c in mocked.call_args_list]
    assert len(bodies) == 2
    assert any("scene 42 moved to Day 8, 2026-11-11" in b for b in bodies) and any("scene 42 moved from Day 7, 2026-11-10" in b for b in bodies)


def test_a_move_racing_a_publish_is_refused_not_merged() -> None:
    """Failure case found in review: the check had to happen under the lock, or the scene ends up on both days."""
    import threading

    from sqlalchemy import text

    from app.database import SessionLocal
    from app.models.call_sheet import CallSheet
    from app.models.production import Production
    from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate, ScheduleItemCreate
    from app.services.call_sheets import create_call_sheet, publish_revision
    from app.services.replan import ReplanConflict, move_scene

    setup = SessionLocal()
    production = Production(name="Race")
    setup.add(production)
    setup.flush()
    scene = ScheduleItemCreate(order_index=1, scene_number="42", int_ext="INT", day_night="DAY", set_description="Set", page_count_eighths=8)
    source = create_call_sheet(setup, production.id, CallSheetCreate(shoot_date="2031-01-01", day_number=1, day_count=2, initial_revision=CallSheetRevisionCreate(schedule_items=[scene])))
    target = create_call_sheet(setup, production.id, CallSheetCreate(shoot_date="2031-01-02", day_number=2, day_count=2, initial_revision=CallSheetRevisionCreate()))
    source_id, target_id = source.id, target.id
    setup.commit()
    setup.close()

    publisher = SessionLocal()
    publisher.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": str(source_id)})
    outcome: dict = {}

    def mover() -> None:
        db = SessionLocal()
        try:
            move_scene(db, db.get(CallSheet, source_id), db.get(CallSheet, target_id), "42", 0, "A", "A", "ad")
            outcome["result"] = "moved"
        except ReplanConflict as exc:
            db.rollback()
            outcome["result"] = str(exc)
        finally:
            db.close()

    thread = threading.Thread(target=mover)
    thread.start()
    thread.join(0.5)  # the move is now waiting on the publisher's lock
    assert thread.is_alive()
    publish_revision(publisher, publisher.get(CallSheet, source_id), CallSheetRevisionCreate(schedule_items=[scene], general_crew_call="06:00"))
    publisher.close()
    thread.join(10)

    assert "REV B" in outcome["result"]
    check = SessionLocal()
    assert [i.scene_number for i in check.get(CallSheet, source_id).current_revision.schedule_items] == ["42"]
    assert check.get(CallSheet, target_id).current_revision.schedule_items == []
    check.close()


def test_a_move_onto_a_planned_day_leaves_no_trace_of_it_for_the_crew(client: TestClient) -> None:
    pid = _production(client)
    d7 = _day(client, pid, 7, "2026-11-10", [_scene("42", 1), _scene("43", 2)])
    planned = _day(client, pid, 8, "2026-11-11", [], draft=True)
    assert _move(client, d7, planned, "42").status_code == 200
    public = client.get(f"/api/v1/public/call-sheets/{d7['id']}").json()
    assert [(c["field"], c["after"], c["other_call_sheet_id"]) for c in public["changes"]] == [("scenes_removed", "42", None)]


def test_moving_the_first_scene_refreshes_what_depends_on_where_the_day_starts(client: TestClient) -> None:
    pid = _production(client)
    a = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "A"}, headers=AUTH).json()["id"]
    b = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "B"}, headers=AUTH).json()["id"]
    d7 = _day(client, pid, 7, "2031-11-10", [{**_scene("42", 1), "location_id": a}, {**_scene("43", 2), "location_id": b}])
    d8 = _day(client, pid, 8, "2031-11-11", [])
    client.post(f"/api/v1/call-sheets/{d7['id']}/revisions", json={"sunrise": "07:00", "sunset": "16:00", "weather_forecast": "Rain", "schedule_items": [{**_scene("42", 1), "location_id": a}, {**_scene("43", 2), "location_id": b}]}, headers=AUTH)
    assert _move(client, d7, d8, "42", letter="B").status_code == 200
    rev = _read(client, d7)["current_revision"]
    assert (rev["sunrise"], rev["weather_forecast"]) == (None, None)  # B has no coordinates here: blank, not A's old values


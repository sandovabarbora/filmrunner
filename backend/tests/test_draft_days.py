"""FR-56: planned (draft) days — invisible to the crew until published, deletable, publish keeps REV A."""

from datetime import date

from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.call_sheets import next_day_for_token

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "Drafts"}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Jana"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Camera", "position": "AC"}, headers=AUTH).json()
    return pid, member


def _scene(n: str, order: int) -> dict:
    return {"order_index": order, "scene_number": n, "int_ext": "EXT", "day_night": "DAY", "set_description": "Set", "page_count_eighths": 8}


def _draft(client: TestClient, pid: str, shoot_date: str, n: int) -> dict:
    r = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": shoot_date, "day_number": n, "day_count": 2, "draft": True,
        "initial_revision": {"general_crew_call": None, "schedule_items": [_scene("42", 1), _scene("43", 2)]},
    }, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def test_draft_is_hidden_from_the_crew_and_skipped_by_the_stable_link(client: TestClient, db_session) -> None:
    pid, member = _setup(client)
    draft = _draft(client, pid, "2026-09-23", 1)
    assert draft["status"] == "draft"
    assert client.get(f"/api/v1/public/call-sheets/{draft['id']}").status_code == 404
    live = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-24", "day_number": 2, "day_count": 2, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []},
    }, headers=AUTH).json()
    nxt = next_day_for_token(db_session, member["personal_token"], date(2026, 9, 22))
    assert str(nxt.call_sheet_id) == live["id"] and [d.day_number for d in nxt.days] == [2]
    # the AD's list still shows it, marked
    days = client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json()
    assert [(d["day_number"], d["status"]) for d in days] == [(1, "draft"), (2, "published")]


def test_publishing_a_draft_replaces_its_content_and_stays_rev_a(client: TestClient) -> None:
    pid, _ = _setup(client)
    draft = _draft(client, pid, "2026-09-23", 1)
    r = client.post(f"/api/v1/call-sheets/{draft['id']}/revisions",
                    json={"general_crew_call": "06:30", "schedule_items": [_scene("42", 1)]}, headers=AUTH)
    assert r.status_code == 201, r.text
    assert r.json()["revision_letter"] == "A"
    sheet = client.get(f"/api/v1/public/call-sheets/{draft['id']}").json()
    assert sheet["status"] == "published" and sheet["previous_revision"] is None and sheet["changes"] == []
    assert [i["scene_number"] for i in sheet["current_revision"]["schedule_items"]] == ["42"]
    # the next one is a real revision B
    r = client.post(f"/api/v1/call-sheets/{draft['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": []}, headers=AUTH)
    assert r.json()["revision_letter"] == "B"


def test_only_a_draft_can_be_deleted(client: TestClient) -> None:
    pid, _ = _setup(client)
    draft = _draft(client, pid, "2026-09-23", 1)
    live = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-24", "day_number": 2, "day_count": 2, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []},
    }, headers=AUTH).json()
    assert client.delete(f"/api/v1/call-sheets/{live['id']}", headers=AUTH).status_code == 409
    assert client.delete(f"/api/v1/call-sheets/{draft['id']}", headers=AUTH).status_code == 204
    assert [d["day_number"] for d in client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json()] == [2]

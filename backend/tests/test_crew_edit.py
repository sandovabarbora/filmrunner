"""FR-18: edit and remove crew members and contacts."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.models.push import PushSubscription

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "Edit crew"}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Petr Malý", "phone": "+420 602 000 000"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Electric", "position": "Best boy"}, headers=AUTH).json()
    return pid, cid, member


def test_patch_member_and_contact(client: TestClient) -> None:
    pid, cid, member = _setup(client)
    resp = client.patch(f"/api/v1/productions/{pid}/crew-members/{member['id']}",
                        json={"position": "Gaffer", "is_head_of_department": True, "standard_call_time": "05:45"}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    assert resp.json()["position"] == "Gaffer" and resp.json()["is_head_of_department"] is True
    assert resp.json()["standard_call_time"] == "05:45"
    assert resp.json()["personal_token"] == member["personal_token"]  # editing never rotates the personal link
    resp = client.patch(f"/api/v1/contacts/{cid}", json={"phone": "+420 777 000 111"}, headers=AUTH)
    assert resp.status_code == 200 and resp.json()["phone"] == "+420 777 000 111"
    assert resp.json()["name"] == "Petr Malý"  # untouched fields stay


def test_remove_member(client: TestClient) -> None:
    pid, cid, member = _setup(client)
    assert client.delete(f"/api/v1/productions/{pid}/crew-members/{member['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/v1/productions/{pid}/crew-members", headers=AUTH).json() == []


def test_removing_the_head_of_day_is_refused(client: TestClient) -> None:
    pid, cid, member = _setup(client)
    client.post(f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 3, "day_count": 9,
                      "initial_revision": {"head_of_day_crew_member_id": member["id"], "schedule_items": []}}, headers=AUTH)
    resp = client.delete(f"/api/v1/productions/{pid}/crew-members/{member['id']}", headers=AUTH)
    assert resp.status_code == 409
    assert "Day 3" in resp.json()["detail"]


def test_removing_a_member_with_an_active_push_subscription_succeeds(client: TestClient, db_session) -> None:
    """FR-79: push_subscriptions.crew_member_id had no ON DELETE clause, so
    Postgres rejected the delete outright with a ForeignKeyViolation."""
    pid, cid, member = _setup(client)
    resp = client.post(
        f"/api/v1/public/crew/{member['personal_token']}/push-subscription",
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/ep1",
            "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"},
            "link_url": "https://filmrunner.example/?sheet=abc&api=https://api.example&me=tok",
        },
    )
    assert resp.status_code == 201, resp.text
    assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).count() == 1

    resp = client.delete(f"/api/v1/productions/{pid}/crew-members/{member['id']}", headers=AUTH)
    assert resp.status_code == 204, resp.text
    assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).count() == 0


def test_member_from_another_production_is_404(client: TestClient) -> None:
    pid, cid, member = _setup(client)
    other = client.post("/api/v1/productions", json={"name": "Other"}, headers=AUTH).json()["id"]
    assert client.patch(f"/api/v1/productions/{other}/crew-members/{member['id']}", json={"position": "x"}, headers=AUTH).status_code == 404


def _crew(client: TestClient, pid: str, name: str) -> str:
    contact = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()["id"]
    return client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "AD", "position": "1st AD"}, headers=AUTH).json()["id"]


def test_someone_who_was_head_of_day_can_be_removed_once_new_revisions_name_someone_else(client: TestClient) -> None:
    """FR-222: only the current revision blocks. History has to give way, not the removal."""
    pid = client.post("/api/v1/productions", json={"name": "Head of day"}, headers=AUTH).json()["id"]
    eva, karel = _crew(client, pid, "Eva"), _crew(client, pid, "Karel")
    day = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2031-02-02", "day_number": 1, "day_count": 1,
        "initial_revision": {"general_crew_call": "07:00", "head_of_day_crew_member_id": eva, "crew_calls": [{"crew_member_id": eva, "call_time": "06:00"}]},
    }, headers=AUTH).json()["id"]

    blocked = client.delete(f"/api/v1/productions/{pid}/crew-members/{eva}", headers=AUTH)
    assert blocked.status_code == 409 and "head of day" in blocked.json()["detail"]

    r = client.post(f"/api/v1/call-sheets/{day}/revisions", json={"general_crew_call": "07:00", "head_of_day_crew_member_id": karel, "crew_calls": []}, headers=AUTH)
    assert r.status_code == 201, r.text
    assert client.delete(f"/api/v1/productions/{pid}/crew-members/{eva}", headers=AUTH).status_code == 204

    sheet = client.get(f"/api/v1/call-sheets/{day}", headers=AUTH).json()
    assert sheet["contacts"]["head_of_day"]["name"] == "Karel"
    history = client.get(f"/api/v1/call-sheets/{day}/history", headers=AUTH)
    assert history.status_code == 200 and [e["revision_letter"] for e in history.json()] == ["A", "B"]
    assert client.delete(f"/api/v1/productions/{pid}/crew-members/{karel}", headers=AUTH).status_code == 409

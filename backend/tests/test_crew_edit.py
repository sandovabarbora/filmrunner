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
            "endpoint": "https://push.example.com/ep1",
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

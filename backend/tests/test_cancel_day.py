"""FR-34: cancel a day (crew told, sheet says so), restore it; rename or wrap a production."""

from datetime import date
from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import push as push_service
from app.services.call_sheets import next_day_for_token

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


@pytest.fixture()
def vapid_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", push_service.generate_keypair()[1])
    return settings


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Cancel test"}, headers=AUTH).json()["id"]


def _day(client: TestClient, pid: str, shoot_date: str, n: int) -> dict:
    r = client.post(f"/api/v1/productions/{pid}/call-sheets",
                    json={"shoot_date": shoot_date, "day_number": n, "day_count": 3, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                    headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def test_cancel_marks_the_sheet_and_restore_undoes_it(client: TestClient) -> None:
    pid = _production(client)
    day = _day(client, pid, "2026-09-23", 1)
    r = client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/public/call-sheets/{day['id']}").json()["status"] == "cancelled"
    assert client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH).status_code == 200  # idempotent
    r = client.post(f"/api/v1/call-sheets/{day['id']}/restore", headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "published"


def test_cancel_tells_every_subscriber(client: TestClient, vapid_configured) -> None:
    pid = _production(client)
    cid = client.post("/api/v1/contacts", json={"name": "Jana"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Camera", "position": "AC"}, headers=AUTH).json()
    client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription",
                json={"endpoint": "https://push.example/abc", "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"}, "link_url": "https://x/?me=t"})
    with patch("app.services.push.webpush"):
        day = _day(client, pid, "2026-09-23", 1)
    with patch("app.services.push.webpush") as mock_webpush:
        r = client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    assert r.json()["current_revision"]["notifications"] == {"attempted": 1, "delivered": 1, "failed": []}
    assert "CANCELLED" in mock_webpush.call_args.kwargs["data"]


def test_stable_link_skips_a_cancelled_day(client: TestClient, db_session) -> None:
    pid = _production(client)
    cid = client.post("/api/v1/contacts", json={"name": "Jana"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Camera", "position": "AC"}, headers=AUTH).json()
    d1 = _day(client, pid, "2026-09-23", 1)
    d2 = _day(client, pid, "2026-09-24", 2)
    client.post(f"/api/v1/call-sheets/{d1['id']}/cancel", headers=AUTH)
    nxt = next_day_for_token(db_session, member["personal_token"], date(2026, 9, 22))
    assert str(nxt.call_sheet_id) == d2["id"]
    assert [(d.day_number, d.status) for d in nxt.days] == [(1, "cancelled"), (2, "published")]


def test_production_rename_and_wrap_need_edit_permission(client: TestClient) -> None:
    pid = _production(client)
    r = client.patch(f"/api/v1/productions/{pid}", json={"name": "  Noc na Karlštejně ", "status": "wrapped"}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Noc na Karlštejně" and r.json()["status"] == "wrapped"
    assert client.patch(f"/api/v1/productions/{pid}", json={"name": "   "}, headers=AUTH).status_code == 422
    assert "production:edit" in r.json()["permissions"]

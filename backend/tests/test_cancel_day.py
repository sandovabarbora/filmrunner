"""FR-34: cancel a day (crew told, sheet says so), restore it; rename or wrap a production."""

from datetime import date
from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import push as push_service
from app.services.call_sheets import next_day_for_token

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}

# FR-78: delivery now happens in a background task with its own DB session;
# see conftest.py's background_tasks_share_db for why this test needs it.
pytestmark = pytest.mark.usefixtures("background_tasks_share_db")


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
                json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"}, "link_url": "https://x/?me=t"})
    with patch("app.services.push.webpush"):
        day = _day(client, pid, "2026-09-23", 1)
    with patch("app.services.push.webpush") as mock_webpush:
        r = client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    # Cumulative for this revision (FR-78's own caveat): one attempt from
    # publishing REV A, a second from cancelling it — cancelling never
    # creates a new revision, so both land on the same history entry.
    history = client.get(f"/api/v1/call-sheets/{day['id']}/history", headers=AUTH).json()
    assert history[-1]["notifications"] == {"attempted": 2, "delivered": 2, "failed": []}
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


# --- FR-222: cancelling and restoring tell the crew what is true, once. ---------------------------

def _crew_with_push(client: TestClient, pid: str) -> dict:
    cid = client.post("/api/v1/contacts", json={"name": "Jana"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Camera", "position": "AC"}, headers=AUTH).json()
    # Asserted: without a subscriber, "nobody was told" would pass for the wrong reason.
    subscribed = client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription",
                             json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"}, "link_url": "https://x/?me=t"})
    assert subscribed.status_code < 300, subscribed.text
    return member


def _draft_day(client: TestClient, pid: str) -> dict:
    r = client.post(f"/api/v1/productions/{pid}/call-sheets",
                    json={"shoot_date": "2031-09-23", "day_number": 1, "day_count": 3, "draft": True, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                    headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def _crew_cannot_reach(client: TestClient, day_id: str, token: str) -> None:
    assert client.get(f"/api/v1/public/call-sheets/{day_id}").status_code == 404
    assert client.get(f"/api/v1/public/call-sheets/{day_id}/me/{token}").status_code == 404
    assert client.post(f"/api/v1/public/call-sheets/{day_id}/seen/{token}").status_code == 404
    assert client.post(f"/api/v1/public/call-sheets/{day_id}/confirm/{token}", json={"revision_letter": "A"}).status_code == 404
    link = client.get(f"/api/v1/public/crew/{token}/next").json()
    assert day_id not in [d["call_sheet_id"] for d in link["days"]] and link["call_sheet_id"] != day_id


def test_a_cancelled_draft_tells_nobody_and_the_crew_cannot_reach_it(client: TestClient, vapid_configured) -> None:
    pid = _production(client)
    member = _crew_with_push(client, pid)
    day = _draft_day(client, pid)
    with patch("app.services.push.webpush") as webpush:
        r = client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["cancelled_from_draft"] is True
    webpush.assert_not_called()
    _crew_cannot_reach(client, day["id"], member["personal_token"])


def test_restoring_a_cancelled_draft_returns_it_to_draft_and_tells_nobody(client: TestClient, vapid_configured) -> None:
    pid = _production(client)
    member = _crew_with_push(client, pid)
    day = _draft_day(client, pid)
    client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    with patch("app.services.push.webpush") as webpush:
        r = client.post(f"/api/v1/call-sheets/{day['id']}/restore", headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "draft" and r.json()["cancelled_from_draft"] is False
    webpush.assert_not_called()
    _crew_cannot_reach(client, day["id"], member["personal_token"])


def test_publishing_a_cancelled_draft_is_still_the_first_thing_the_crew_sees(client: TestClient) -> None:
    """Otherwise the crew's first sight of the day would be a REV B replacing a REV A they never had."""
    pid = _production(client)
    day = _draft_day(client, pid)
    client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    r = client.post(f"/api/v1/call-sheets/{day['id']}/revisions", json={"general_crew_call": "07:00"}, headers=AUTH)
    assert r.status_code == 201 and r.json()["revision_letter"] == "A"
    public = client.get(f"/api/v1/public/call-sheets/{day['id']}").json()
    assert public["status"] == "published" and public["cancelled_from_draft"] is False and public["changes"] == []


def test_a_cancelled_draft_can_be_deleted_since_nobody_saw_it(client: TestClient) -> None:
    pid = _production(client)
    day = _draft_day(client, pid)
    client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    assert client.delete(f"/api/v1/call-sheets/{day['id']}", headers=AUTH).status_code == 204


def test_a_cancelled_published_day_can_still_not_be_deleted(client: TestClient) -> None:
    pid = _production(client)
    day = _day(client, pid, "2031-09-23", 1)
    client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    assert client.delete(f"/api/v1/call-sheets/{day['id']}", headers=AUTH).status_code == 409


def test_a_repeat_cancel_does_not_notify_again(client: TestClient, vapid_configured) -> None:
    pid = _production(client)
    _crew_with_push(client, pid)
    with patch("app.services.push.webpush"):
        day = _day(client, pid, "2031-09-23", 1)
    with patch("app.services.push.webpush") as webpush:
        client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
        assert webpush.call_count == 1 and "CANCELLED" in webpush.call_args.kwargs["data"]
        assert client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH).status_code == 200
        assert webpush.call_count == 1


def test_restoring_a_published_day_tells_the_crew_once(client: TestClient, vapid_configured) -> None:
    pid = _production(client)
    _crew_with_push(client, pid)
    with patch("app.services.push.webpush"):
        day = _day(client, pid, "2031-09-23", 1)
        client.post(f"/api/v1/call-sheets/{day['id']}/cancel", headers=AUTH)
    with patch("app.services.push.webpush") as webpush:
        r = client.post(f"/api/v1/call-sheets/{day['id']}/restore", headers=AUTH)
        assert r.json()["status"] == "published"
        assert webpush.call_count == 1 and "BACK ON" in webpush.call_args.kwargs["data"]
        assert client.post(f"/api/v1/call-sheets/{day['id']}/restore", headers=AUTH).status_code == 200
        assert webpush.call_count == 1
    assert client.get(f"/api/v1/public/call-sheets/{day['id']}").json()["status"] == "published"

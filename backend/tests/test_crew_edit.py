"""FR-18: edit and remove crew members and contacts."""

from fastapi.testclient import TestClient

from app.config import get_settings

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


def test_member_from_another_production_is_404(client: TestClient) -> None:
    pid, cid, member = _setup(client)
    other = client.post("/api/v1/productions", json={"name": "Other"}, headers=AUTH).json()["id"]
    assert client.patch(f"/api/v1/productions/{other}/crew-members/{member['id']}", json={"position": "x"}, headers=AUTH).status_code == 404

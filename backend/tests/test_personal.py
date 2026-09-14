"""FR-13: a crew member's personal link shows their own call and department first."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "Personal"}, headers=AUTH).json()["id"]
    c1 = client.post("/api/v1/contacts", json={"name": "Eva Dvořáková", "phone": "+420 777 111 222"}, headers=AUTH).json()["id"]
    c2 = client.post("/api/v1/contacts", json={"name": "Petr Malý", "phone": "+420 602 000 000"}, headers=AUTH).json()["id"]
    hod = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": c1, "department": "Electric", "position": "Gaffer", "is_head_of_department": True}, headers=AUTH).json()
    petr = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": c2, "department": "Electric", "position": "Best boy", "standard_call_time": "06:00"}, headers=AUTH).json()
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH).json()
    return pid, hod, petr, sheet


def test_crew_member_gets_a_personal_token_and_the_public_me_endpoint(client: TestClient) -> None:
    pid, hod, petr, sheet = _setup(client)
    assert petr["personal_token"] and len(petr["personal_token"]) >= 16
    me = client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/{petr['personal_token']}")
    assert me.status_code == 200
    body = me.json()
    assert body["name"] == "Petr Malý"
    assert body["department"] == "Electric" and body["position"] == "Best boy"
    assert body["personal_call"] == "06:00"  # own standard call beats the general call
    assert body["department_head"]["name"] == "Eva Dvořáková"


def test_personal_call_falls_back_to_the_general_crew_call(client: TestClient) -> None:
    pid, hod, petr, sheet = _setup(client)
    me = client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/{hod['personal_token']}").json()
    assert me["personal_call"] == "06:30"
    assert me["department_head"]["name"] == "Eva Dvořáková"  # the HoD's own department head is themselves


def test_wrong_token_or_wrong_production_is_404(client: TestClient) -> None:
    pid, hod, petr, sheet = _setup(client)
    assert client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/not-a-token").status_code == 404
    other = client.post("/api/v1/productions", json={"name": "Other"}, headers=AUTH).json()["id"]
    other_sheet = client.post(f"/api/v1/productions/{other}/call-sheets", json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"schedule_items": []}}, headers=AUTH).json()
    assert client.get(f"/api/v1/public/call-sheets/{other_sheet['id']}/me/{petr['personal_token']}").status_code == 404  # token from another production

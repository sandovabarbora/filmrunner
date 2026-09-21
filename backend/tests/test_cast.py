"""FR-33: cast members and per-day cast calls with status codes."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Cast test"}, headers=AUTH).json()["id"]


def _actor(client: TestClient, pid: str, name: str, character: str) -> dict:
    cid = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()["id"]
    r = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": cid, "character_name": character, "standard_pickup_time": "05:30"}, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def _sheet(client: TestClient, pid: str, cast_calls: list | None) -> dict:
    body = {"shoot_date": "2026-09-23", "day_number": 1, "day_count": 3,
            "initial_revision": {"general_crew_call": "06:30", "schedule_items": [], **({"cast_calls": cast_calls} if cast_calls is not None else {})}}
    r = client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def test_cast_member_crud_carries_the_contact(client: TestClient) -> None:
    pid = _production(client)
    actor = _actor(client, pid, "Anna Geislerová", "MARTA")
    assert actor["contact"]["name"] == "Anna Geislerová" and actor["character_name"] == "MARTA"
    listed = client.get(f"/api/v1/productions/{pid}/cast-members", headers=AUTH).json()
    assert [a["id"] for a in listed] == [actor["id"]]
    r = client.patch(f"/api/v1/productions/{pid}/cast-members/{actor['id']}", json={"character_name": "MARTA (older)"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["character_name"] == "MARTA (older)"
    other = _production(client)
    assert client.patch(f"/api/v1/productions/{other}/cast-members/{actor['id']}", json={"character_name": "x"}, headers=AUTH).status_code == 404
    assert client.delete(f"/api/v1/productions/{pid}/cast-members/{actor['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/v1/productions/{pid}/cast-members", headers=AUTH).json() == []


def test_cast_calls_appear_named_on_the_public_sheet_in_call_order(client: TestClient) -> None:
    pid = _production(client)
    a = _actor(client, pid, "Anna Geislerová", "MARTA")
    b = _actor(client, pid, "Karel Roden", "OTEC")
    sheet = _sheet(client, pid, [
        {"cast_member_id": b["id"], "status_code": "SW", "pickup_time": "07:00", "call_time": "07:30", "makeup_hair_time": "07:45", "on_set_time": "09:00"},
        {"cast_member_id": a["id"], "status_code": "W", "pickup_time": "05:30", "call_time": "06:00", "makeup_hair_time": "06:15", "on_set_time": "08:00"},
    ])
    rows = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["cast_calls"]
    assert [(r["name"], r["character_name"], r["status_code"], r["call_time"]) for r in rows] == [
        ("Anna Geislerová", "MARTA", "W", "06:00"), ("Karel Roden", "OTEC", "SW", "07:30"),
    ]


def test_cast_calls_copy_forward_and_a_foreign_actor_is_refused(client: TestClient) -> None:
    pid = _production(client)
    a = _actor(client, pid, "Anna Geislerová", "MARTA")
    sheet = _sheet(client, pid, [{"cast_member_id": a["id"], "status_code": "W", "call_time": "06:00"}])
    # REV B without cast_calls keeps Anna; REV C with [] clears her.
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": []}, headers=AUTH)
    assert [r["name"] for r in client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["cast_calls"]] == ["Anna Geislerová"]
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": [], "cast_calls": []}, headers=AUTH)
    assert client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["cast_calls"] == []

    stranger = _actor(client, _production(client), "Someone", "ELSE")
    r = client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions",
                    json={"general_crew_call": "07:00", "schedule_items": [], "cast_calls": [{"cast_member_id": stranger["id"], "status_code": "W"}]}, headers=AUTH)
    assert r.status_code == 422


def test_removing_an_actor_with_calls_on_a_sheet_keeps_the_sheet_publishable(client: TestClient) -> None:
    """Failure case: the sheet outlives the person; their line is dropped, publishing goes on."""
    pid = _production(client)
    a = _actor(client, pid, "Anna Geislerová", "MARTA")
    sheet = _sheet(client, pid, [{"cast_member_id": a["id"], "status_code": "W", "call_time": "06:00"}])
    assert client.delete(f"/api/v1/productions/{pid}/cast-members/{a['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["cast_calls"] == []
    r = client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": []}, headers=AUTH)
    assert r.status_code == 201, r.text

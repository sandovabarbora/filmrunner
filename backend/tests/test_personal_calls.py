"""FR-24: per-day personal call times on a revision, copied forward, precedence over standing times."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _crew(client: TestClient, pid: str, name: str, standing: str | None = None) -> str:
    cid = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()["id"]
    return client.post(f"/api/v1/productions/{pid}/crew-members",
                       json={"contact_id": cid, "department": "Electric", "position": "Gaffer", "standard_call_time": standing}, headers=AUTH).json()


def test_day_entry_beats_standing_time_beats_general_call(client: TestClient) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Calls"}, headers=AUTH).json()["id"]
    a = _crew(client, pid, "A", standing="06:00")
    b = _crew(client, pid, "B", standing="06:00")
    c = _crew(client, pid, "C")
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-29", "day_number": 1, "day_count": 1,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": [],
                             "crew_calls": [{"crew_member_id": a["id"], "call_time": "05:15", "pickup_time": "04:45", "note": "generator first"}]}}, headers=AUTH)
    assert sheet.status_code == 201, sheet.text
    sid = sheet.json()["id"]
    me = lambda m: client.get(f"/api/v1/public/call-sheets/{sid}/me/{m['personal_token']}").json()
    assert me(a)["personal_call"] == "05:15" and me(a)["pickup_time"] == "04:45" and me(a)["note"] == "generator first"
    assert me(b)["personal_call"] == "06:00"  # standing time
    assert me(c)["personal_call"] == "06:30"  # general call
    public = client.get(f"/api/v1/public/call-sheets/{sid}").json()
    assert [(p["name"], p["call_time"]) for p in public["personal_calls"]] == [("A", "05:15")]


def test_entries_copy_forward_unless_replaced(client: TestClient) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Copy"}, headers=AUTH).json()["id"]
    a = _crew(client, pid, "A")
    sid = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-29", "day_number": 1, "day_count": 1,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": [], "crew_calls": [{"crew_member_id": a["id"], "call_time": "05:15"}]}}, headers=AUTH).json()["id"]
    # REV B without crew_calls: copied forward
    b = client.post(f"/api/v1/call-sheets/{sid}/revisions", json={"general_crew_call": "07:00", "schedule_items": []}, headers=AUTH).json()
    assert [e["call_time"] for e in b["crew_calls"]] == ["05:15"]
    # REV C with an explicit empty list: cleared
    c = client.post(f"/api/v1/call-sheets/{sid}/revisions", json={"general_crew_call": "07:00", "schedule_items": [], "crew_calls": []}, headers=AUTH).json()
    assert c["crew_calls"] == []


def test_entry_for_a_foreign_crew_member_is_rejected_and_removed_member_drops_entry(client: TestClient) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Guard"}, headers=AUTH).json()["id"]
    other = client.post("/api/v1/productions", json={"name": "Other"}, headers=AUTH).json()["id"]
    foreign = _crew(client, other, "X")
    resp = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-29", "day_number": 1, "day_count": 1,
        "initial_revision": {"schedule_items": [], "crew_calls": [{"crew_member_id": foreign["id"], "call_time": "05:00"}]}}, headers=AUTH)
    assert resp.status_code == 422
    mine = _crew(client, pid, "M")
    sid = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-29", "day_number": 1, "day_count": 1,
        "initial_revision": {"schedule_items": [], "crew_calls": [{"crew_member_id": mine["id"], "call_time": "05:00"}]}}, headers=AUTH).json()["id"]
    assert client.delete(f"/api/v1/productions/{pid}/crew-members/{mine['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/v1/public/call-sheets/{sid}").json()["personal_calls"] == []
    # publishing after the removal still works (entries dropped, not dangling)
    assert client.post(f"/api/v1/call-sheets/{sid}/revisions", json={"schedule_items": []}, headers=AUTH).status_code == 201

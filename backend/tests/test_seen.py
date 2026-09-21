"""FR-36: who has opened REV B."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "Seen"}, headers=AUTH).json()["id"]
    members = []
    for name, dept in (("Tomáš Novák", "Electric"), ("Eva Malá", "Camera")):
        cid = client.post("/api/v1/contacts", json={"name": name, "phone": "777 000 111"}, headers=AUTH).json()["id"]
        members.append(client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": dept, "position": "x"}, headers=AUTH).json())
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets",
                        json={"shoot_date": "2026-09-23", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                        headers=AUTH).json()
    return pid, members, sheet


def test_seen_is_per_revision_and_idempotent(client: TestClient) -> None:
    pid, (tomas, eva), sheet = _setup(client)
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert report["revision_letter"] == "A" and report["seen"] == [] and [e["name"] for e in report["not_seen"]] == ["Eva Malá", "Tomáš Novák"]

    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{tomas['personal_token']}").status_code == 204
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{tomas['personal_token']}").status_code == 204  # again: same row
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert [e["name"] for e in report["seen"]] == ["Tomáš Novák"] and report["seen"][0]["seen_at"]
    assert [e["name"] for e in report["not_seen"]] == ["Eva Malá"]
    assert report["not_seen"][0]["phone"] == "777 000 111" and report["not_seen"][0]["personal_token"] == eva["personal_token"]

    # REV B starts the count over: Tomáš has not seen B yet.
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": []}, headers=AUTH)
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert report["revision_letter"] == "B" and report["seen"] == []


def test_unknown_or_foreign_token_is_refused(client: TestClient) -> None:
    _, _, sheet = _setup(client)
    _, (stranger, _), _ = _setup(client)
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/nope").status_code == 404
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{stranger['personal_token']}").status_code == 404


def test_removing_a_crew_member_removes_their_receipt(client: TestClient) -> None:
    pid, (tomas, _), sheet = _setup(client)
    client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{tomas['personal_token']}")
    assert client.delete(f"/api/v1/productions/{pid}/crew-members/{tomas['id']}", headers=AUTH).status_code == 204
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert report["seen"] == [] and [e["name"] for e in report["not_seen"]] == ["Eva Malá"]

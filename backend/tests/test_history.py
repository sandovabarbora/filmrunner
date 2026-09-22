"""FR-50: publish history on the day screen — who published each revision,
when, what it changed versus the one before, and how many crew opened it."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "History"}, headers=AUTH).json()["id"]
    members = []
    for name, dept in (("Tomáš Novák", "Electric"), ("Eva Malá", "Camera")):
        cid = client.post("/api/v1/contacts", json={"name": name, "phone": "777 000 111"}, headers=AUTH).json()["id"]
        members.append(client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": dept, "position": "x"}, headers=AUTH).json())
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets",
                        json={"shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
                              "initial_revision": {"general_crew_call": "06:30", "schedule_items": [], "created_by": "editor"}},
                        headers=AUTH).json()
    return pid, members, sheet


def test_history_has_one_line_per_revision_with_author_changes_and_opened_count(client: TestClient) -> None:
    pid, (tomas, _), sheet = _setup(client)
    history = client.get(f"/api/v1/call-sheets/{sheet['id']}/history", headers=AUTH).json()
    assert len(history) == 1
    assert history[0]["revision_letter"] == "A"
    assert history[0]["created_by"] == "service:editor"
    assert history[0]["changes"] == []  # REV A never shows a diff against nothing
    assert history[0]["opened"] == 0

    client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{tomas['personal_token']}")
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions",
               json={"general_crew_call": "07:00", "schedule_items": [], "created_by": "editor"}, headers=AUTH)
    history = client.get(f"/api/v1/call-sheets/{sheet['id']}/history", headers=AUTH).json()
    assert [h["revision_letter"] for h in history] == ["A", "B"]
    assert history[0]["opened"] == 1  # REV A's own receipt is untouched by REV B existing
    assert history[1]["opened"] == 0
    assert history[1]["changes"] == [{"field": "crew_call", "label": "Crew call", "before": "06:30", "after": "07:00"}]


def test_history_shows_unknown_for_a_revision_with_no_recorded_author(client: TestClient, db_session) -> None:
    """A revision published before `created_by` existed, or by a script that named nobody, must never show
    an empty cell (dod failure case)."""
    from app.models.call_sheet import CallSheetRevision

    _, _, sheet = _setup(client)
    rev = db_session.query(CallSheetRevision).filter(CallSheetRevision.call_sheet_id == sheet["id"]).one()
    rev.created_by = None
    db_session.commit()
    history = client.get(f"/api/v1/call-sheets/{sheet['id']}/history", headers=AUTH).json()
    assert history[0]["created_by"] == "unknown"


def test_history_requires_production_read(client: TestClient) -> None:
    _, _, sheet = _setup(client)
    assert client.get(f"/api/v1/call-sheets/{sheet['id']}/history").status_code == 401

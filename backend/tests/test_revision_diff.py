"""FR-23: what changed between the last two revisions, on the public read."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _sheet(client: TestClient, pid: str, revision: dict) -> dict:
    body = {"shoot_date": "2026-09-23", "day_number": 2, "day_count": 5, "initial_revision": revision}
    r = client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Diff"}, headers=AUTH).json()["id"]


def _scene(n: str, order: int) -> dict:
    return {"order_index": order, "scene_number": n, "int_ext": "INT", "day_night": "DAY", "set_description": "Set", "page_count_eighths": 8}


def test_only_rev_a_has_no_previous_and_no_changes(client: TestClient) -> None:
    """Failure case: a sheet with only REV A must not show an empty "replaces" sentence."""
    sheet = _sheet(client, _production(client), {"general_crew_call": "06:30", "schedule_items": []})
    read = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()
    assert read["previous_revision"] is None
    assert read["changes"] == []


def test_changed_calls_scene_order_and_notes_are_listed(client: TestClient) -> None:
    sheet = _sheet(client, _production(client), {
        "general_crew_call": "06:30", "shooting_call": "08:00", "safety_notes": "Stairs",
        "schedule_items": [_scene("7", 1), _scene("12A", 2)],
    })
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={
        "general_crew_call": "07:30", "shooting_call": "08:00", "safety_notes": "Stairs, wet",
        "schedule_items": [_scene("12A", 1), _scene("7", 2)],
    }, headers=AUTH)
    read = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()
    assert read["previous_revision"]["revision_letter"] == "A"
    assert read["previous_revision"]["created_at"]
    by_field = {c["field"]: c for c in read["changes"]}
    assert by_field["crew_call"] == {"field": "crew_call", "label": "Crew call", "before": "06:30", "after": "07:30"}
    assert by_field["scene_order"]["before"] == "7, 12A" and by_field["scene_order"]["after"] == "12A, 7"
    assert by_field["safety_notes"]["after"] == "Stairs, wet"
    assert "shooting_call" not in by_field  # unchanged fields are left out


def test_diff_is_against_the_immediately_previous_revision(client: TestClient) -> None:
    """REV C compares with B, not A: a crew call changed in B and kept in C is not reported again."""
    sheet = _sheet(client, _production(client), {"general_crew_call": "06:30", "schedule_items": []})
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:30", "schedule_items": []}, headers=AUTH)
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:30", "safety_notes": "Rain", "schedule_items": []}, headers=AUTH)
    read = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()
    assert read["previous_revision"]["revision_letter"] == "B"
    assert [c["field"] for c in read["changes"]] == ["safety_notes"]

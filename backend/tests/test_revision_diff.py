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
    assert by_field["crew_call"] == {"field": "crew_call", "label": "Crew call", "before": "06:30", "after": "07:30", "scenes": []}
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


def _publish(client: TestClient, sheet_id: str, revision: dict) -> list[dict]:
    r = client.post(f"/api/v1/call-sheets/{sheet_id}/revisions", json=revision, headers=AUTH)
    assert r.status_code == 201, r.text
    return client.get(f"/api/v1/public/call-sheets/{sheet_id}").json()["changes"]


def _location(client: TestClient, pid: str, name: str) -> str:
    return client.post(f"/api/v1/productions/{pid}/locations", json={"name": name}, headers=AUTH).json()["id"]


def _crew(client: TestClient, pid: str, name: str) -> str:
    contact = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()
    return client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact["id"], "department": "AD", "position": "1st AD"}, headers=AUTH).json()["id"]


def _cast(client: TestClient, pid: str, name: str) -> str:
    contact = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()
    return client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact["id"], "character_name": "MARTA"}, headers=AUTH).json()["id"]


def test_a_scene_moving_location_is_listed_with_both_names(client: TestClient) -> None:
    """The evening-before case: same call, same order, another place. The crew must not drive to the old one."""
    pid = _production(client)
    troja, studio = _location(client, pid, "Troja"), _location(client, pid, "Studio")
    scenes = [{**_scene("42", 1), "location_id": troja}, {**_scene("43", 2), "location_id": troja}, {**_scene("44", 3), "location_id": studio}]
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": scenes})
    changes = _publish(client, sheet["id"], {"general_crew_call": "07:00", "schedule_items": [{**s, "location_id": studio} for s in scenes]})
    assert changes == [{"field": "location", "label": "Location, sc 42, 43", "before": "Troja", "after": "Studio", "scenes": ["42", "43"]}]


def test_scene_content_changes_name_only_what_moved(client: TestClient) -> None:
    sheet = _sheet(client, _production(client), {"schedule_items": [_scene("42", 1)]})
    changes = _publish(client, sheet["id"], {"schedule_items": [{**_scene("42", 1), "int_ext": "EXT", "day_night": "NIGHT", "set_description": "Rain cover", "page_count_eighths": 11}]})
    assert changes == [{"field": "scene_detail", "label": "Scene 42", "before": "INT DAY · Set · 1 pg", "after": "EXT NIGHT · Rain cover · 1 3/8 pg", "scenes": ["42"]}]


def test_added_and_removed_scenes_are_not_reported_as_a_new_order(client: TestClient) -> None:
    sheet = _sheet(client, _production(client), {"schedule_items": [_scene("1", 1), _scene("2", 2), _scene("3", 3)]})
    changes = _publish(client, sheet["id"], {"schedule_items": [_scene("1", 1), _scene("3", 2), _scene("4", 3)]})
    assert [(c["field"], c["after"], c["scenes"]) for c in changes] == [("scenes_added", "4", ["4"]), ("scenes_removed", "2", ["2"])]


def test_a_scene_shot_in_two_parts_pairs_up_with_itself(client: TestClient) -> None:
    """Failure case: pairing by scene number alone would report the second part as the first one changing."""
    sheet = _sheet(client, _production(client), {"schedule_items": [{**_scene("7", 1), "set_description": "Part one"}, {**_scene("7", 2), "set_description": "Part two"}]})
    changes = _publish(client, sheet["id"], {"schedule_items": [{**_scene("7", 1), "set_description": "Part one"}, {**_scene("7", 2), "set_description": "Part two, longer"}]})
    assert [(c["field"], c["after"]) for c in changes] == [("scene_detail", "Part two, longer")]


def test_cast_call_changes_name_the_actor(client: TestClient) -> None:
    pid = _production(client)
    actor = _cast(client, pid, "Anna Geislerová")
    sheet = _sheet(client, pid, {"schedule_items": [], "cast_calls": [{"cast_member_id": actor, "status_code": "W", "pickup_time": "06:00"}]})
    changes = _publish(client, sheet["id"], {"schedule_items": [], "cast_calls": [{"cast_member_id": actor, "status_code": "W", "pickup_time": "05:30"}]})
    assert [(c["field"], c["after"]) for c in changes] == [("cast_calls", "Anna Geislerová")]


def test_every_field_of_a_revision_shows_up_in_the_diff(client: TestClient) -> None:
    """The guarantee behind the push text: nothing a crew member relies on can change silently. Adding a revision
    field fails the first assertion until it is compared in revision_changes and listed here."""
    pid = _production(client)
    troja, studio = _location(client, pid, "Troja"), _location(client, pid, "Studio")
    head, other = _crew(client, pid, "Eva"), _crew(client, pid, "Jana")
    actor = _cast(client, pid, "Anna")
    scene = {**_scene("42", 1), "location_id": troja}
    cast = {"cast_member_id": actor, "status_code": "W", "pickup_time": "06:00", "call_time": "06:30", "makeup_hair_time": "07:00", "on_set_time": "08:00"}
    crew = {"crew_member_id": other, "call_time": "05:00", "pickup_time": "04:30", "note": "Pre-rig"}
    base = {
        "general_crew_call": "07:00", "shooting_call": "08:00", "sunrise": "07:10", "sunset": "16:20", "weather_forecast": "Rain",
        "safety_notes": "Stairs", "head_of_day_crew_member_id": head, "schedule_items": [scene], "cast_calls": [cast], "crew_calls": [crew],
    }
    mutations = {
        "general_crew_call": {"general_crew_call": "06:30"}, "shooting_call": {"shooting_call": "07:30"}, "sunrise": {"sunrise": "07:11"},
        "sunset": {"sunset": "16:21"}, "weather_forecast": {"weather_forecast": "Snow"}, "safety_notes": {"safety_notes": "Ice"},
        "head_of_day_crew_member_id": {"head_of_day_crew_member_id": other},
        "scene_number": {"schedule_items": [{**scene, "scene_number": "99"}]}, "int_ext": {"schedule_items": [{**scene, "int_ext": "EXT"}]},
        "day_night": {"schedule_items": [{**scene, "day_night": "NIGHT"}]}, "set_description": {"schedule_items": [{**scene, "set_description": "New"}]},
        "location_id": {"schedule_items": [{**scene, "location_id": studio}]}, "page_count_eighths": {"schedule_items": [{**scene, "page_count_eighths": 3}]},
        "status_code": {"cast_calls": [{**cast, "status_code": "H"}]}, "cast_pickup": {"cast_calls": [{**cast, "pickup_time": "05:00"}]},
        "cast_call": {"cast_calls": [{**cast, "call_time": "05:30"}]}, "makeup_hair_time": {"cast_calls": [{**cast, "makeup_hair_time": "05:45"}]},
        "on_set_time": {"cast_calls": [{**cast, "on_set_time": "09:00"}]}, "crew_call": {"crew_calls": [{**crew, "call_time": "04:00"}]},
        "crew_pickup": {"crew_calls": [{**crew, "pickup_time": "03:30"}]}, "crew_note": {"crew_calls": [{**crew, "note": "Rig"}]},
    }
    from app.schemas.call_sheet import CallSheetRevisionCreate, CastCallEntryCreate, CrewCallEntryCreate, ScheduleItemCreate
    assert set(CallSheetRevisionCreate.model_fields) == {"general_crew_call", "shooting_call", "sunrise", "sunset", "weather_forecast", "safety_notes", "created_by", "head_of_day_crew_member_id", "schedule_items", "cast_calls", "crew_calls"}
    assert set(ScheduleItemCreate.model_fields) == {"order_index", "scene_number", "int_ext", "day_night", "set_description", "location_id", "page_count_eighths"}
    assert set(CastCallEntryCreate.model_fields) == {"cast_member_id", "status_code", "pickup_time", "call_time", "makeup_hair_time", "on_set_time"}
    assert set(CrewCallEntryCreate.model_fields) == {"crew_member_id", "call_time", "pickup_time", "note"}

    for name, patch in mutations.items():
        sheet = _sheet(client, pid, base)
        assert _publish(client, sheet["id"], {**base, **patch}), f"changing {name} produced an empty diff"


def test_republishing_identical_content_says_so(client: TestClient) -> None:
    from app.services.call_sheets import change_summary
    sheet = _sheet(client, _production(client), {"general_crew_call": "07:00", "schedule_items": [_scene("1", 1)]})
    assert _publish(client, sheet["id"], {"general_crew_call": "07:00", "schedule_items": [_scene("1", 1)]}) == []
    assert change_summary([]) == "republished, content unchanged"


def test_the_push_line_shows_two_changes_and_counts_the_rest() -> None:
    from app.schemas.call_sheet import RevisionChange
    from app.services.call_sheets import change_summary
    rows = [
        RevisionChange(field="crew_call", label="Crew call", before="07:00", after="06:30"),
        RevisionChange(field="location", label="Location, sc 42", before="Troja", after="S" * 90),
        RevisionChange(field="scenes_removed", label="Scenes removed", before=None, after="9"),
    ]
    line = change_summary(rows)
    assert line.startswith("crew call 07:00 → 06:30; location, sc 42 Troja → SSS")
    assert line.endswith("… (+1 more)")
    assert len(line) < 130

"""FR-23: what changed between the last two revisions, on the public read."""

NO_MOVE = {"other_call_sheet_id": None, "other_day_number": None, "other_date": None}

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
    assert by_field["crew_call"] == {"field": "crew_call", "label": "Crew call", "before": "06:30", "after": "07:30", "scenes": [], **NO_MOVE}
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
    assert changes == [{"field": "location", "label": "Location, sc 42, 43", "before": "Troja", "after": "Studio", "scenes": ["42", "43"], **NO_MOVE}]


def test_scene_content_changes_name_only_what_moved(client: TestClient) -> None:
    sheet = _sheet(client, _production(client), {"schedule_items": [_scene("42", 1)]})
    changes = _publish(client, sheet["id"], {"schedule_items": [{**_scene("42", 1), "int_ext": "EXT", "day_night": "NIGHT", "set_description": "Rain cover", "page_count_eighths": 11}]})
    assert changes == [{"field": "scene_detail", "label": "Scene 42", "before": "INT DAY · Set · 1 pg", "after": "EXT NIGHT · Rain cover · 1 3/8 pg", "scenes": ["42"], **NO_MOVE}]


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
    assert set(CallSheetRevisionCreate.model_fields) == {"general_crew_call", "shooting_call", "sunrise", "sunset", "weather_forecast", "safety_notes", "created_by", "expected_revision_id", "head_of_day_crew_member_id", "schedule_items", "cast_calls", "crew_calls"}
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


def _crew_full(client: TestClient, pid: str, name: str, standing: str | None = None) -> dict:
    contact = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()
    return client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact["id"], "department": "Electric", "position": "Gaffer", "standard_call_time": standing}, headers=AUTH).json()


def _me(client: TestClient, sheet_id: str, member: dict) -> dict:
    return client.get(f"/api/v1/public/call-sheets/{sheet_id}/me/{member['personal_token']}").json()


def test_a_moved_personal_call_says_what_it_was(client: TestClient) -> None:
    pid = _production(client)
    gaffer, dop = _crew_full(client, pid, "Tomáš"), _crew_full(client, pid, "Marek")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    _publish(client, sheet["id"], {"general_crew_call": "07:00", "schedule_items": [], "crew_calls": [{"crew_member_id": gaffer["id"], "call_time": "05:00", "pickup_time": "04:30"}]})
    me = _me(client, sheet["id"], gaffer)
    assert (me["personal_call"], me["call_before"], me["pickup_time"], me["pickup_before"]) == ("05:00", "07:00", "04:30", None)
    other = _me(client, sheet["id"], dop)
    assert (other["personal_call"], other["call_before"]) == ("07:00", None)


def test_a_moved_crew_call_counts_as_your_call_only_if_it_is_yours(client: TestClient) -> None:
    """Failure case: someone on a standing time must not be told their call moved when the crew call did."""
    pid = _production(client)
    floating, standing = _crew_full(client, pid, "Jana"), _crew_full(client, pid, "Petr", standing="05:00")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    _publish(client, sheet["id"], {"general_crew_call": "06:30", "schedule_items": []})
    assert _me(client, sheet["id"], floating)["call_before"] == "07:00"
    assert _me(client, sheet["id"], standing)["call_before"] is None


def test_rev_a_never_has_a_before(client: TestClient) -> None:
    pid = _production(client)
    member = _crew_full(client, pid, "Jana")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    assert _me(client, sheet["id"], member)["call_before"] is None


def _confirm(client: TestClient, sheet_id: str, member: dict, letter: str):
    return client.post(f"/api/v1/public/call-sheets/{sheet_id}/confirm/{member['personal_token']}", json={"revision_letter": letter})


def _report(client: TestClient, sheet_id: str) -> dict:
    report = client.get(f"/api/v1/call-sheets/{sheet_id}/seen", headers=AUTH).json()
    return {e["name"]: e for e in report["seen"] + report["not_seen"]}


def test_confirming_is_per_revision_and_the_ad_sees_it(client: TestClient) -> None:
    pid = _production(client)
    gaffer, dop = _crew_full(client, pid, "Tomáš"), _crew_full(client, pid, "Marek")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    r = _confirm(client, sheet["id"], gaffer, "A")
    assert r.status_code == 200 and r.json()["revision_letter"] == "A"
    entries = _report(client, sheet["id"])
    assert entries["Tomáš"]["confirmed_at"] and entries["Tomáš"]["seen_at"]  # confirming implies it was opened
    assert entries["Marek"]["confirmed_at"] is None
    assert _me(client, sheet["id"], gaffer)["confirmed_at"]
    days = client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json()
    assert (days[0]["opened"]["confirmed"], days[0]["opened"]["total"]) == (1, 2)

    _publish(client, sheet["id"], {"general_crew_call": "06:30", "schedule_items": []})
    assert _report(client, sheet["id"])["Tomáš"]["confirmed_at"] is None  # REV B starts over
    me = _me(client, sheet["id"], gaffer)
    assert me["confirmed_at"] is None and me["revision_letter"] == "B"
    assert dop["id"]


def test_confirming_a_replaced_revision_is_refused(client: TestClient) -> None:
    """Failure case: a phone still showing REV A must not record "I know" against the plan that replaced it."""
    pid = _production(client)
    gaffer = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    _publish(client, sheet["id"], {"general_crew_call": "06:30", "schedule_items": []})
    assert _confirm(client, sheet["id"], gaffer, "A").status_code == 409
    assert _report(client, sheet["id"])["Tomáš"]["confirmed_at"] is None


def test_confirming_twice_keeps_the_first_time(client: TestClient) -> None:
    pid = _production(client)
    gaffer = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"schedule_items": []})
    first = _confirm(client, sheet["id"], gaffer, "A").json()["confirmed_at"]
    assert _confirm(client, sheet["id"], gaffer, "A").json()["confirmed_at"] == first


def test_confirm_needs_a_real_token_and_a_live_day(client: TestClient) -> None:
    pid = _production(client)
    gaffer = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"schedule_items": []})
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/confirm/nobody", json={"revision_letter": "A"}).status_code == 404
    client.post(f"/api/v1/call-sheets/{sheet['id']}/cancel", headers=AUTH)
    assert _confirm(client, sheet["id"], gaffer, "A").status_code == 403


def _seen(client: TestClient, sheet_id: str, member: dict) -> None:
    assert client.post(f"/api/v1/public/call-sheets/{sheet_id}/seen/{member['personal_token']}").status_code == 204


def _skip_to_rev_c(client: TestClient, sheet_id: str) -> None:
    """B moves the crew call, C only a safety note, so "what changed in C" alone would hide the new call."""
    _publish(client, sheet_id, {"general_crew_call": "06:00", "schedule_items": []})
    _publish(client, sheet_id, {"general_crew_call": "06:00", "safety_notes": "Ice", "schedule_items": []})


def test_someone_who_confirmed_an_old_revision_sees_everything_since(client: TestClient) -> None:
    pid = _production(client)
    member = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    assert _confirm(client, sheet["id"], member, "A").status_code == 200
    _skip_to_rev_c(client, sheet["id"])
    me = _me(client, sheet["id"], member)
    assert me["since_letter"] == "A"
    assert [(c["field"], c["before"], c["after"]) for c in me["changes_since"] if c["field"] == "crew_call"] == [("crew_call", "07:00", "06:00")]
    assert me["call_before"] == "07:00"  # the time they actually know


def test_opening_counts_when_nothing_was_confirmed(client: TestClient) -> None:
    pid = _production(client)
    member = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    _seen(client, sheet["id"], member)
    _skip_to_rev_c(client, sheet["id"])
    assert _me(client, sheet["id"], member)["since_letter"] == "A"


def test_a_confirmation_beats_a_later_open(client: TestClient) -> None:
    """Failure case: opening REV B without confirming must not move the baseline past what they said they know."""
    pid = _production(client)
    member = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    _confirm(client, sheet["id"], member, "A")
    _publish(client, sheet["id"], {"general_crew_call": "06:00", "schedule_items": []})
    _seen(client, sheet["id"], member)
    _publish(client, sheet["id"], {"general_crew_call": "06:00", "safety_notes": "Ice", "schedule_items": []})
    assert _me(client, sheet["id"], member)["since_letter"] == "A"


def test_no_catching_up_when_the_normal_diff_covers_it(client: TestClient) -> None:
    pid = _production(client)
    member, stranger = _crew_full(client, pid, "Tomáš"), _crew_full(client, pid, "Nový")
    sheet = _sheet(client, pid, {"general_crew_call": "07:00", "schedule_items": []})
    _confirm(client, sheet["id"], member, "A")
    _publish(client, sheet["id"], {"general_crew_call": "06:00", "schedule_items": []})
    me = _me(client, sheet["id"], member)
    assert me["since_letter"] is None and me["changes_since"] is None
    _publish(client, sheet["id"], {"general_crew_call": "05:00", "schedule_items": []})
    assert _me(client, sheet["id"], stranger)["since_letter"] is None  # never read anything: the current revision is news as a whole
    _confirm(client, sheet["id"], member, "C")
    assert _me(client, sheet["id"], member)["since_letter"] is None  # caught up


def test_times_on_the_wire_say_they_are_utc(client: TestClient) -> None:
    """A browser reads a zoneless time as local: "issued 21:40" for a revision out at 22:40 in Prague."""
    pid = _production(client)
    member = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"schedule_items": []})
    read = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()
    assert read["current_revision"]["created_at"].endswith(("Z", "+00:00"))
    assert _confirm(client, sheet["id"], member, "A").json()["confirmed_at"].endswith(("Z", "+00:00"))
    assert _me(client, sheet["id"], member)["confirmed_at"].endswith(("Z", "+00:00"))


def test_a_removed_note_is_a_change_for_that_person(client: TestClient) -> None:
    """Failure case found in review: "nothing changes for you" while their pre-rig note had just gone."""
    pid = _production(client)
    member = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"schedule_items": [], "crew_calls": [{"crew_member_id": member["id"], "note": "Pre-rig"}]})
    _publish(client, sheet["id"], {"schedule_items": [], "crew_calls": []})
    assert _me(client, sheet["id"], member)["note_changed"] is True


def test_confirming_works_with_or_without_a_prior_receipt_and_twice(client: TestClient) -> None:
    pid = _production(client)
    member = _crew_full(client, pid, "Tomáš")
    sheet = _sheet(client, pid, {"schedule_items": []})
    _seen(client, sheet["id"], member)
    _seen(client, sheet["id"], member)
    assert _confirm(client, sheet["id"], member, "A").status_code == 200
    _seen(client, sheet["id"], member)
    entries = _report(client, sheet["id"])
    assert entries["Tomáš"]["confirmed_at"] and entries["Tomáš"]["seen_at"]


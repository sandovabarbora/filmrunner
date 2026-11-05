"""FR-205: an actor's own link, their own times, and a place on the AD's confirmation list."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "Cast links"}, headers=AUTH).json()["id"]
    contact = client.post("/api/v1/contacts", json={"name": "Anna Geislerová", "phone": "+420603555010"}, headers=AUTH).json()["id"]
    actor = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact, "character_name": "MARTA"}, headers=AUTH).json()
    return pid, actor


def _day(client: TestClient, pid: str, actor: dict | None, date: str = "2026-11-10", pickup: str = "06:00") -> dict:
    calls = [{"cast_member_id": actor["id"], "status_code": "W", "pickup_time": pickup, "call_time": "06:30", "makeup_hair_time": "06:45", "on_set_time": "08:00"}] if actor else []
    body = {"shoot_date": date, "day_number": 7, "day_count": 24, "initial_revision": {"general_crew_call": "05:00", "schedule_items": [], "cast_calls": calls}}
    return client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH).json()


def _me(client: TestClient, sheet: dict, actor: dict):
    return client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/{actor['personal_token']}")


def test_an_actors_link_shows_their_own_times_and_never_the_crew_call(client: TestClient) -> None:
    pid, actor = _setup(client)
    me = _me(client, _day(client, pid, actor), actor).json()
    assert me["is_cast"] and me["works_today"]
    assert (me["name"], me["position"]) == ("Anna Geislerová", "MARTA")
    assert (me["personal_call"], me["pickup_time"], me["makeup_hair_time"], me["on_set_time"]) == ("06:30", "06:00", "06:45", "08:00")


def test_an_actor_not_called_today_has_no_call(client: TestClient) -> None:
    """Failure case: falling back to the crew call would send them to set on a day they are not working."""
    pid, actor = _setup(client)
    me = _me(client, _day(client, pid, None), actor).json()
    assert not me["works_today"] and me["personal_call"] is None


def test_a_moved_pickup_says_what_it_was(client: TestClient) -> None:
    pid, actor = _setup(client)
    sheet = _day(client, pid, actor)
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "05:00", "schedule_items": [],
                "cast_calls": [{"cast_member_id": actor["id"], "status_code": "W", "pickup_time": "05:30", "call_time": "06:30"}]}, headers=AUTH)
    me = _me(client, sheet, actor).json()
    assert (me["pickup_time"], me["pickup_before"], me["call_before"]) == ("05:30", "06:00", None)


def test_the_ad_sees_a_called_actor_on_the_list_and_their_confirmation(client: TestClient) -> None:
    pid, actor = _setup(client)
    sheet = _day(client, pid, actor)
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    entry = next(e for e in report["not_seen"] if e["is_cast"])
    assert (entry["name"], entry["position"], entry["phone"]) == ("Anna Geislerová", "MARTA", "+420603555010")

    r = client.post(f"/api/v1/public/call-sheets/{sheet['id']}/confirm/{actor['personal_token']}", json={"revision_letter": "A"})
    assert r.status_code == 200
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert next(e for e in report["seen"] if e["is_cast"])["confirmed_at"]
    days = client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json()
    assert (days[0]["opened"]["confirmed"], days[0]["opened"]["total"]) == (1, 1)


def test_an_actor_not_called_today_is_not_chased(client: TestClient) -> None:
    pid, _actor = _setup(client)
    sheet = _day(client, pid, None)
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert report["not_seen"] == [] and report["seen"] == []


def test_the_stable_link_opens_for_an_actor(client: TestClient) -> None:
    pid, actor = _setup(client)
    sheet = _day(client, pid, actor, date="2099-01-01")
    next_day = client.get(f"/api/v1/public/crew/{actor['personal_token']}/next").json()
    assert next_day["call_sheet_id"] == sheet["id"] and next_day["crew_member_name"] == "Anna Geislerová"


def test_an_actors_token_is_nobody_on_another_production(client: TestClient) -> None:
    pid, actor = _setup(client)
    other_pid = client.post("/api/v1/productions", json={"name": "Other"}, headers=AUTH).json()["id"]
    other_sheet = _day(client, other_pid, None)
    _day(client, pid, actor)
    assert _me(client, other_sheet, actor).status_code == 404
    assert client.post(f"/api/v1/public/call-sheets/{other_sheet['id']}/seen/{actor['personal_token']}").status_code == 404
    assert client.post(f"/api/v1/public/call-sheets/{other_sheet['id']}/confirm/{actor['personal_token']}", json={"revision_letter": "A"}).status_code == 404


def test_removing_an_actor_removes_their_receipts(client: TestClient) -> None:
    pid, actor = _setup(client)
    sheet = _day(client, pid, actor)
    client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{actor['personal_token']}")
    assert client.delete(f"/api/v1/productions/{pid}/cast-members/{actor['id']}", headers=AUTH).status_code == 204
    report = client.get(f"/api/v1/call-sheets/{sheet['id']}/seen", headers=AUTH).json()
    assert report["seen"] == [] and report["not_seen"] == []

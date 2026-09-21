"""FR-32: one link per person for the whole shoot — where it opens."""

from datetime import date

from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.call_sheets import next_day_for_token

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _setup(client: TestClient, dates: list[str]) -> tuple[str, str]:
    pid = client.post("/api/v1/productions", json={"name": "Shoot"}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Tomáš Novák"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members",
                         json={"contact_id": cid, "department": "Electric", "position": "Gaffer"}, headers=AUTH).json()
    for i, d in enumerate(dates, start=1):
        r = client.post(f"/api/v1/productions/{pid}/call-sheets",
                        json={"shoot_date": d, "day_number": i, "day_count": len(dates), "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                        headers=AUTH)
        assert r.status_code == 201, r.text
    return pid, member["personal_token"]


def test_opens_the_next_day_today_included_then_the_last_one_after_wrap(client: TestClient, db_session) -> None:
    _, token = _setup(client, ["2026-09-21", "2026-09-22", "2026-09-24"])
    before = next_day_for_token(db_session, token, date(2026, 9, 20))
    today = next_day_for_token(db_session, token, date(2026, 9, 22))
    gap = next_day_for_token(db_session, token, date(2026, 9, 23))
    after = next_day_for_token(db_session, token, date(2026, 10, 1))
    by_date = {d.shoot_date.isoformat(): str(d.call_sheet_id) for d in before.days}
    assert str(before.call_sheet_id) == by_date["2026-09-21"]
    assert str(today.call_sheet_id) == by_date["2026-09-22"]
    assert str(gap.call_sheet_id) == by_date["2026-09-24"]
    assert str(after.call_sheet_id) == by_date["2026-09-24"]  # the shoot is over: the last sheet stays useful
    assert [d.day_number for d in before.days] == [1, 2, 3]
    assert before.crew_member_name == "Tomáš Novák" and before.production_name == "Shoot"


def test_public_endpoint_resolves_and_rejects_unknown_tokens(client: TestClient) -> None:
    _, token = _setup(client, ["2099-01-01"])
    r = client.get(f"/api/v1/public/crew/{token}/next")
    assert r.status_code == 200, r.text
    assert r.json()["call_sheet_id"] == r.json()["days"][0]["call_sheet_id"]
    assert r.json()["days"][0]["revision_letter"] == "A"
    assert client.get("/api/v1/public/crew/not-a-token/next").status_code == 404


def test_production_without_days_yet_gives_no_sheet_not_an_error(client: TestClient) -> None:
    _, token = _setup(client, [])
    r = client.get(f"/api/v1/public/crew/{token}/next")
    assert r.status_code == 200
    assert r.json()["call_sheet_id"] is None and r.json()["days"] == []


def test_each_day_carries_its_crew_call_and_first_location(client: TestClient, monkeypatch) -> None:
    """FR-42: the sheet can say "Tomorrow: crew call 06:30 · Karlštejn" from the stable-link answer alone."""
    from app.routers import productions as productions_router
    monkeypatch.setattr(productions_router.geocoding, "geocode", lambda address: None)
    pid, token = _setup(client, ["2026-09-21"])
    loc = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Karlštejn"}, headers=AUTH).json()
    client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-22", "day_number": 2, "day_count": 2,
        "initial_revision": {"general_crew_call": "07:15", "schedule_items": [
            {"order_index": 1, "scene_number": "3", "int_ext": "EXT", "day_night": "DAY", "set_description": "Gate", "page_count_eighths": 8, "location_id": loc["id"]},
        ]},
    }, headers=AUTH)
    days = client.get(f"/api/v1/public/crew/{token}/next").json()["days"]
    assert [(d["day_number"], d["general_crew_call"], d["first_location_name"]) for d in days] == [(1, "06:30", None), (2, "07:15", "Karlštejn")]

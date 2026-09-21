"""FR-35: where the day happens, on the public sheet."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.routers import productions as productions_router
from app.services import call_sheets as call_sheets_service
from app.services.geocoding import GeocodeResult

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _scene(n: str, order: int, location_id: str | None) -> dict:
    return {"order_index": order, "scene_number": n, "int_ext": "EXT", "day_night": "DAY", "set_description": "Set", "page_count_eighths": 8, "location_id": location_id}


def test_locations_listed_in_schedule_order_with_their_scenes(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(productions_router.geocoding, "geocode", lambda address: GeocodeResult(lat=50.08, lng=14.42, display_name="Praha") if address else None)
    # Not this test's concern (FR-39 covers weather separately); stub it out
    # so publish doesn't make a real network call here.
    monkeypatch.setattr(call_sheets_service.weather, "weather_suggestion", lambda lat, lng, on_date: None)
    pid = client.post("/api/v1/productions", json={"name": "Loc"}, headers=AUTH).json()["id"]
    castle = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Karlštejn", "address": "Karlštejn 172", "parking_notes": "Lower car park"}, headers=AUTH).json()
    studio = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Studio B"}, headers=AUTH).json()
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": [
            _scene("12", 1, studio["id"]), _scene("7", 2, castle["id"]), _scene("8", 3, castle["id"]), _scene("9", 4, None),
        ]},
    }, headers=AUTH).json()
    locs = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["locations"]
    assert [(l["name"], l["scene_numbers"]) for l in locs] == [("Studio B", ["12"]), ("Karlštejn", ["7", "8"])]
    assert locs[1]["address"] == "Karlštejn 172" and locs[1]["parking_notes"] == "Lower car park" and locs[1]["geo_lat"] == 50.08
    assert locs[0]["address"] is None and locs[0]["geo_lat"] is None


def test_no_located_scene_means_no_locations_not_an_error(client: TestClient) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Loc"}, headers=AUTH).json()["id"]
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-23", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": [_scene("1", 1, None)]},
    }, headers=AUTH).json()
    assert client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["locations"] == []

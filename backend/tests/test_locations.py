"""FR-19: geocoding on location save, weather/nearest-hospital suggestion
endpoints, and sunrise/sunset auto-computed on publish from the day's
first scheduled location. Geocoding/weather/hospital calls are monkeypatched
at the service module used by the router — see test_location_services.py
for the services' own request/response handling."""

import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.routers import productions as productions_router
from app.services import call_sheets as call_sheets_service
from app.services.geocoding import GeocodeResult

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Locations test"}, headers=AUTH).json()["id"]


def test_create_location_geocodes_address(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0870, lng=14.4208, display_name="Staroměstské náměstí, Praha 1, Česko"),
    )
    pid = _production(client)
    resp = client.post(
        f"/api/v1/productions/{pid}/locations",
        json={"name": "Old Town Square", "address": "Staroměstské náměstí, Praha"},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["geo_lat"] == 50.0870
    assert body["geo_lng"] == 14.4208
    assert body["geocoded_display_name"] == "Staroměstské náměstí, Praha 1, Česko"


def test_create_location_without_address_skips_geocoding(client: TestClient, monkeypatch) -> None:
    def fail(*a, **k):
        raise AssertionError("should not geocode without an address")

    monkeypatch.setattr(productions_router.geocoding, "geocode", fail)
    pid = _production(client)
    resp = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Studio, no address yet"}, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["geo_lat"] is None


def test_create_location_geocoder_miss_leaves_coordinates_editable_and_empty(client: TestClient, monkeypatch) -> None:
    """Failure case: the fields stay editable and empty rather than the
    request failing — the sheet never waits on / is blocked by a third party."""
    monkeypatch.setattr(productions_router.geocoding, "geocode", lambda address: None)
    pid = _production(client)
    resp = client.post(
        f"/api/v1/productions/{pid}/locations", json={"name": "Somewhere unmapped", "address": "??"}, headers=AUTH
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["geo_lat"] is None and body["geocoded_display_name"] is None


def test_update_location_regeocodes_only_when_address_changes(client: TestClient, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: calls.append(address) or GeocodeResult(lat=1.0, lng=2.0, display_name=f"resolved: {address}"),
    )
    pid = _production(client)
    loc_id = client.post(
        f"/api/v1/productions/{pid}/locations", json={"name": "Set A", "address": "Address 1"}, headers=AUTH
    ).json()["id"]
    assert calls == ["Address 1"]

    # Editing an unrelated field must not re-geocode.
    resp = client.patch(f"/api/v1/productions/{pid}/locations/{loc_id}", json={"parking_notes": "Behind the church"}, headers=AUTH)
    assert resp.status_code == 200
    assert calls == ["Address 1"]

    # Changing the address re-geocodes.
    resp = client.patch(f"/api/v1/productions/{pid}/locations/{loc_id}", json={"address": "Address 2"}, headers=AUTH)
    assert resp.status_code == 200
    assert calls == ["Address 1", "Address 2"]
    assert resp.json()["geocoded_display_name"] == "resolved: Address 2"


def test_weather_suggestion_without_coordinates_returns_null(client: TestClient) -> None:
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "No address"}, headers=AUTH).json()["id"]
    resp = client.get(f"/api/v1/productions/{pid}/locations/{loc_id}/weather-suggestion", params={"shoot_date": "2026-06-21"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"suggestion": None}


def test_weather_suggestion_with_coordinates_calls_the_service(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(productions_router.geocoding, "geocode", lambda address: GeocodeResult(lat=50.0, lng=14.0, display_name="X"))
    seen = {}

    def fake(lat, lng, on_date):
        seen["args"] = (lat, lng, on_date)
        return "9-18°C, slight rain"

    monkeypatch.setattr(productions_router.weather, "weather_suggestion", fake)
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Loc", "address": "A"}, headers=AUTH).json()["id"]
    resp = client.get(f"/api/v1/productions/{pid}/locations/{loc_id}/weather-suggestion", params={"shoot_date": "2026-06-21"}, headers=AUTH)
    assert resp.json() == {"suggestion": "9-18°C, slight rain"}
    assert seen["args"][0] == 50.0 and seen["args"][1] == 14.0


def test_hospital_suggestion_with_coordinates_calls_the_service(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(productions_router.geocoding, "geocode", lambda address: GeocodeResult(lat=50.0, lng=14.0, display_name="X"))
    monkeypatch.setattr(productions_router.hospitals, "nearest_hospital_suggestion", lambda lat, lng: "FN Motol, V Úvalu 84")
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Loc", "address": "A"}, headers=AUTH).json()["id"]
    resp = client.get(f"/api/v1/productions/{pid}/locations/{loc_id}/hospital-suggestion", headers=AUTH)
    assert resp.json() == {"suggestion": "FN Motol, V Úvalu 84"}


def test_publish_computes_sunrise_sunset_from_first_located_scene(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0755, lng=14.4378, display_name="Prague"),
    )
    # Not this test's concern (FR-39 covers weather separately); stub it out
    # so publish doesn't make a real network call here.
    monkeypatch.setattr(call_sheets_service.weather, "weather_suggestion", lambda lat, lng, on_date: None)
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Riverbank", "address": "Troja, Praha"}, headers=AUTH).json()["id"]
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-06-21", "day_number": 1, "day_count": 1,
            "initial_revision": {
                "general_crew_call": "05:00",
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
                                     "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc_id}],
            },
        },
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    rev = resp.json()["current_revision"]
    assert rev["sunrise"] is not None and rev["sunset"] is not None
    # 2026-06-21 near the summer solstice at Prague's latitude: sanity bounds, not exact-minute.
    assert "04:" in rev["sunrise"] or "05:" in rev["sunrise"]
    assert "21:" in rev["sunset"]


def test_publish_does_not_overwrite_sunrise_typed_by_the_ad(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0755, lng=14.4378, display_name="Prague"),
    )
    monkeypatch.setattr(call_sheets_service.weather, "weather_suggestion", lambda lat, lng, on_date: None)
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Riverbank", "address": "Troja"}, headers=AUTH).json()["id"]
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-06-21", "day_number": 1, "day_count": 1,
            "initial_revision": {
                "sunrise": "05:00", "sunset": "21:30",
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
                                     "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc_id}],
            },
        },
        headers=AUTH,
    )
    rev = resp.json()["current_revision"]
    assert rev["sunrise"] == "05:00"
    assert rev["sunset"] == "21:30"


def test_publish_without_located_scenes_leaves_sunrise_sunset_null(client: TestClient) -> None:
    pid = _production(client)
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-06-21", "day_number": 1, "day_count": 1, "initial_revision": {"schedule_items": []}},
        headers=AUTH,
    )
    rev = resp.json()["current_revision"]
    assert rev["sunrise"] is None and rev["sunset"] is None


def test_publish_fills_weather_forecast_from_first_located_scene_when_blank(client: TestClient, monkeypatch) -> None:
    """FR-39: like sunrise/sunset, a blank weather line fills in on publish
    from the day's first located scene, with the same text the "Suggest
    weather" button would give."""
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0755, lng=14.4378, display_name="Prague"),
    )
    monkeypatch.setattr(call_sheets_service.weather, "weather_suggestion", lambda lat, lng, on_date: "9-18°C, slight rain")
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Riverbank", "address": "Troja, Praha"}, headers=AUTH).json()["id"]
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-06-21", "day_number": 1, "day_count": 1,
            "initial_revision": {
                "general_crew_call": "05:00",
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
                                     "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc_id}],
            },
        },
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["current_revision"]["weather_forecast"] == "9-18°C, slight rain"


def test_publish_does_not_overwrite_weather_typed_by_the_ad(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0755, lng=14.4378, display_name="Prague"),
    )

    def fail(*a, **k):
        raise AssertionError("should not fetch a weather suggestion when the AD already typed one")

    monkeypatch.setattr(call_sheets_service.weather, "weather_suggestion", fail)
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Riverbank", "address": "Troja"}, headers=AUTH).json()["id"]
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-06-21", "day_number": 1, "day_count": 1,
            "initial_revision": {
                "weather_forecast": "Jasno, 20°C",
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
                                     "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc_id}],
            },
        },
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["current_revision"]["weather_forecast"] == "Jasno, 20°C"


def test_publish_succeeds_and_leaves_weather_blank_when_the_provider_is_down(client: TestClient, monkeypatch) -> None:
    """Failure case: the provider being unreachable never fails or delays a
    publish — weather_suggestion already returns None on any failure within
    its own timeout, so publish just leaves the field blank."""
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0755, lng=14.4378, display_name="Prague"),
    )
    monkeypatch.setattr(call_sheets_service.weather, "weather_suggestion", lambda lat, lng, on_date: None)
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Riverbank", "address": "Troja"}, headers=AUTH).json()["id"]
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-06-21", "day_number": 1, "day_count": 1,
            "initial_revision": {
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
                                     "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc_id}],
            },
        },
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["current_revision"]["weather_forecast"] is None


def test_sun_times_for_a_geocoded_location_and_none_without_coordinates(client: TestClient, monkeypatch) -> None:
    """FR-27: the editor asks for sunrise/sunset as soon as a location is picked; no coordinates means no guess, not an error."""
    monkeypatch.setattr(
        productions_router.geocoding, "geocode",
        lambda address: GeocodeResult(lat=50.0870, lng=14.4208, display_name="Praha") if address else None,
    )
    pid = _production(client)
    mapped = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Square", "address": "Staroměstské náměstí"}, headers=AUTH).json()
    unmapped = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "TBD"}, headers=AUTH).json()

    resp = client.get(f"/api/v1/productions/{pid}/locations/{mapped['id']}/sun?shoot_date=2026-09-23", headers=AUTH)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sunrise"].startswith("06:") and body["sunset"].startswith("18:")  # Prague, late September

    resp = client.get(f"/api/v1/productions/{pid}/locations/{unmapped['id']}/sun?shoot_date=2026-09-23", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"sunrise": None, "sunset": None}


def test_delete_location_drops_the_link_on_a_scene_that_used_it_and_the_day_still_publishes(client: TestClient) -> None:
    """FR-38 dod: scenes on any revision that pointed to the deleted location
    keep their text and lose the link (location_id null); the sheet's Where
    block simply drops it, and the day still loads and can publish again."""
    pid = _production(client)
    loc_id = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Riverbank"}, headers=AUTH).json()["id"]
    resp = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-06-21", "day_number": 1, "day_count": 1,
            "initial_revision": {
                "general_crew_call": "06:30",
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
                                     "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc_id}],
            },
        },
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    sheet_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/productions/{pid}/locations/{loc_id}", headers=AUTH)
    assert resp.status_code == 204, resp.text

    resp = client.get(f"/api/v1/productions/{pid}/locations", headers=AUTH)
    assert resp.json() == []

    resp = client.get(f"/api/v1/call-sheets/{sheet_id}", headers=AUTH)
    assert resp.status_code == 200, resp.text
    item = resp.json()["current_revision"]["schedule_items"][0]
    assert item["set_description"] == "Riverbank"
    assert item["location_id"] is None
    assert resp.json()["locations"] == []

    # The day still loads and can publish another revision after the location is gone.
    resp = client.post(
        f"/api/v1/call-sheets/{sheet_id}/revisions",
        json={"general_crew_call": "06:45", "schedule_items": [
            {"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY",
             "set_description": "Riverbank", "page_count_eighths": 8, "location_id": None},
        ]},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["revision_letter"] == "B"


def test_delete_location_that_does_not_exist_returns_404(client: TestClient) -> None:
    pid = _production(client)
    resp = client.delete(f"/api/v1/productions/{pid}/locations/{uuid.uuid4()}", headers=AUTH)
    assert resp.status_code == 404

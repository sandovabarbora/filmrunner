"""FR-53: export a production through the API and import it into an empty one — field for field on the public sheet."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.routers import productions as productions_router
from app.services.geocoding import GeocodeResult
from scripts import production_backup as backup

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


@pytest.fixture()
def through_test_client(client: TestClient, monkeypatch):
    """Point the script's HTTP helper at the TestClient instead of the network."""
    def call(method: str, path: str, body=None):
        r = client.request(method, path, json=body, headers=AUTH)
        assert r.status_code < 400, f"{method} {path} → {r.status_code}: {r.text}"
        return r.json() if r.content else None
    monkeypatch.setattr(backup, "call", call)
    monkeypatch.setattr(productions_router.geocoding, "geocode", lambda address: GeocodeResult(lat=50.08, lng=14.42, display_name="Praha") if address else None)
    return client


def _build(client: TestClient) -> str:
    pid = client.post("/api/v1/productions", json={"name": "Backup me", "status": "shooting"}, headers=AUTH).json()["id"]
    c1 = client.post("/api/v1/contacts", json={"name": "Eva Dvořáková", "phone": "+420 777 111 222"}, headers=AUTH).json()["id"]
    c2 = client.post("/api/v1/contacts", json={"name": "Anna Geislerová", "phone": None}, headers=AUTH).json()["id"]
    hod = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": c1, "department": "AD", "position": "1st AD", "is_head_of_department": True, "standard_call_time": "05:45"}, headers=AUTH).json()
    actor = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": c2, "character_name": "MARTA", "standard_pickup_time": "05:30"}, headers=AUTH).json()
    loc = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Troja", "address": "Trojská 1", "parking_notes": "Gravel lot"}, headers=AUTH).json()
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "viewer@example.com", "role": "viewer"}, headers=AUTH)
    client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-23", "day_number": 1, "day_count": 2, "initial_revision": {
            "general_crew_call": "06:30", "shooting_call": "07:30", "safety_notes": "Water", "head_of_day_crew_member_id": hod["id"],
            "schedule_items": [{"order_index": 1, "scene_number": "42", "int_ext": "EXT", "day_night": "DAY", "set_description": "RIVERBANK", "page_count_eighths": 14, "location_id": loc["id"]}],
            "cast_calls": [{"cast_member_id": actor["id"], "status_code": "SW", "pickup_time": "05:30", "call_time": "06:00"}],
            "crew_calls": [{"crew_member_id": hod["id"], "call_time": "05:15", "note": "first"}],
        }}, headers=AUTH)
    d2 = client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": "2026-09-24", "day_number": 2, "day_count": 2, "initial_revision": {"general_crew_call": "07:00", "schedule_items": []}}, headers=AUTH).json()
    client.post(f"/api/v1/call-sheets/{d2['id']}/cancel", headers=AUTH)
    return pid


def _public_shape(client: TestClient, pid: str) -> list:
    """Everything a crew member would see, with ids stripped, per day."""
    out = []
    for d in client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json():
        sheet = client.get(f"/api/v1/call-sheets/{d['id']}", headers=AUTH).json()
        rev = sheet["current_revision"]
        out.append({
            "date": sheet["shoot_date"], "n": sheet["day_number"], "status": sheet["status"], "letter": rev["revision_letter"],
            "calls": (rev["general_crew_call"], rev["shooting_call"], rev["safety_notes"]),
            "scenes": [(i["scene_number"], i["set_description"], i["page_count_eighths"]) for i in rev["schedule_items"]],
            "cast": [(c["name"], c["character_name"], c["status_code"], c["call_time"]) for c in sheet["cast_calls"]],
            "personal": [(p["name"], p["call_time"], p["note"]) for p in sheet["personal_calls"]],
            "where": [(l["name"], l["address"], l["parking_notes"], l["geo_lat"]) for l in sheet["locations"]],
            "hod": sheet["contacts"]["head_of_day"]["name"] if sheet["contacts"]["head_of_day"] else None,
        })
    return out


def test_export_then_import_reproduces_the_sheets(through_test_client: TestClient) -> None:
    client = through_test_client
    src = _build(client)
    data = json.loads(json.dumps(backup.export_production(src)))  # through JSON, like a file
    assert data["format"] == 1 and len(data["days"]) == 2 and len(data["contacts"]) == 2
    dst = backup.import_production(data)
    assert dst != src
    assert _public_shape(client, dst) == _public_shape(client, src)
    assert [m["email"] for m in client.get(f"/api/v1/productions/{dst}/members", headers=AUTH).json() if m["role"] == "viewer"] == ["viewer@example.com"]
    # crew got new personal tokens: old links are not resurrected by a restore
    old_tok = client.get(f"/api/v1/productions/{src}/crew-members", headers=AUTH).json()[0]["personal_token"]
    new_tok = client.get(f"/api/v1/productions/{dst}/crew-members", headers=AUTH).json()[0]["personal_token"]
    assert old_tok != new_tok


def test_import_into_a_non_empty_production_is_refused(through_test_client: TestClient) -> None:
    client = through_test_client
    src = _build(client)
    data = backup.export_production(src)
    with pytest.raises(SystemExit, match="import only into an empty one"):
        backup.import_production(data, into=src)
    empty = client.post("/api/v1/productions", json={"name": "Empty"}, headers=AUTH).json()["id"]
    assert backup.import_production(data, into=empty) == empty
    assert len(client.get(f"/api/v1/productions/{empty}/call-sheets", headers=AUTH).json()) == 2

"""FR-52: pilot scale on a phone — 60 crew, 8 cast, 6 locations, 30 days of 40–60 scenes, 5 personal calls a day.

Seeds one production through the API (idempotent by name within the test database), then measures on an
iPhone-width viewport with a throttled 4G profile (CDP: 4 Mbit/s down, 1 Mbit/s up, 150 ms RTT):
time to a usable screen for the days list, a day screen, the crew tab and the crew's public sheet, plus
API response sizes. Prints a table (run with -s) and asserts the one hard line in the dod: the public
sheet of a 60-scene day renders under 2 s on the throttled profile.
"""

import json
import time
import urllib.request

import pytest
from playwright.sync_api import Page, expect

from conftest import E2E_TOKEN
from test_editor_e2e import _connect

NAME = "Scale test (FR-52) v2"
DEPARTMENTS = ["AD", "Camera", "Electric", "Grip", "Sound", "Art", "Costume", "Make-up", "Production", "Locations", "Transport", "Catering"]
POSITIONS = ["Head", "1st", "2nd", "Assistant", "Trainee"]


def _api(api_url: str, method: str, path: str, body=None):
    req = urllib.request.Request(api_url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {E2E_TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


@pytest.fixture(scope="module")
def scale_production(api_url: str) -> dict:
    """The seeded production: {id, day_ids, biggest_day_id, token}."""
    existing = [p for p in _api(api_url, "GET", "/api/v1/productions") if p["name"] == NAME]
    if existing:
        pid = existing[0]["id"]
        crew = _api(api_url, "GET", f"/api/v1/productions/{pid}/crew-members")
        days = _api(api_url, "GET", f"/api/v1/productions/{pid}/call-sheets")
    else:
        pid = _api(api_url, "POST", "/api/v1/productions", {"name": NAME, "status": "shooting"})["id"]
        crew = []
        for i in range(60):
            dept = DEPARTMENTS[i % len(DEPARTMENTS)]
            cid = _api(api_url, "POST", "/api/v1/contacts", {"name": f"{dept} Person {i + 1}", "phone": f"+420 7{i:02d} 000 {i:03d}"})["id"]
            crew.append(_api(api_url, "POST", f"/api/v1/productions/{pid}/crew-members", {
                "contact_id": cid, "department": dept, "position": POSITIONS[(i // len(DEPARTMENTS)) % len(POSITIONS)],
                "is_head_of_department": i < len(DEPARTMENTS), "standard_call_time": None}))
        cast = []
        for i in range(8):
            cid = _api(api_url, "POST", "/api/v1/contacts", {"name": f"Actor {i + 1}"})["id"]
            cast.append(_api(api_url, "POST", f"/api/v1/productions/{pid}/cast-members", {"contact_id": cid, "character_name": f"ROLE {i + 1}", "standard_pickup_time": "05:30"}))
        locations = [_api(api_url, "POST", f"/api/v1/productions/{pid}/locations", {
            "name": f"Location {i + 1}", "address": f"Street {i + 1}, Praha", "parking_notes": "Yard, 10 cars", "nearest_hospital": "Bulovka",
            "geo_lat": 50.08 + i * 0.01, "geo_lng": 14.42 + i * 0.01}) for i in range(6)]
        days = []
        for d in range(30):
            n_scenes = 40 + (d * 5) % 21  # 40–60, day 5 has 60
            scenes = [{"order_index": s + 1, "scene_number": f"{d * 60 + s + 1}", "int_ext": "EXT" if s % 3 else "INT", "day_night": "NIGHT" if s % 5 == 0 else "DAY",
                       "set_description": f"SET {s + 1} — a description long enough to wrap on a phone, like a real slugline would",
                       "page_count_eighths": 3 + s % 9, "location_id": locations[s % 6]["id"]} for s in range(n_scenes)]
            days.append(_api(api_url, "POST", f"/api/v1/productions/{pid}/call-sheets", {
                "shoot_date": f"2099-03-{(d % 28) + 1:02d}" if d < 28 else f"2099-04-{d - 27:02d}", "day_number": d + 1, "day_count": 30,
                "initial_revision": {
                    "general_crew_call": "06:30", "shooting_call": "07:30", "safety_notes": "Stairs, water, animals on set" if d % 2 else None,
                    "head_of_day_crew_member_id": crew[0]["id"], "schedule_items": scenes,
                    "cast_calls": [{"cast_member_id": c["id"], "status_code": "W", "pickup_time": "05:30", "call_time": "06:00", "makeup_hair_time": "06:15", "on_set_time": "07:30"} for c in cast[:5]],
                    "crew_calls": [{"crew_member_id": crew[k]["id"], "call_time": "05:15", "note": "early"} for k in range(1, 6)],
                }}))
    biggest = next(d for d in days if d["day_number"] == 5)  # 40 + (4*5) % 21 = 60 scenes; the list read carries no scenes (FR-52)
    n_big = len(_api(api_url, "GET", f"/api/v1/call-sheets/{biggest['id']}")["current_revision"]["schedule_items"])
    return {"id": pid, "day_ids": [d["id"] for d in days], "biggest_day_id": biggest["id"], "n_big": n_big, "token": crew[7]["personal_token"], "days": days}


def _throttle(page: Page) -> None:
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150, "downloadThroughput": 4_000_000 // 8, "uploadThroughput": 1_000_000 // 8})


def _timed(page: Page, url: str, selector: str, ready=None) -> float:
    t0 = time.perf_counter()
    page.goto(url)
    page.wait_for_selector(selector, timeout=30_000)
    if ready:
        ready()
    return round(time.perf_counter() - t0, 2)


def test_pilot_scale_on_a_throttled_phone(page: Page, frontend_url: str, api_url: str, scale_production: dict) -> None:
    pid, big, token, n_big = scale_production["id"], scale_production["biggest_day_id"], scale_production["token"], scale_production["n_big"]
    assert n_big == 60
    sizes = {}
    for label, path in (("days list", f"/api/v1/productions/{pid}/call-sheets"), ("biggest day", f"/api/v1/call-sheets/{big}"),
                        ("crew", f"/api/v1/productions/{pid}/crew-members"), ("public sheet", f"/api/v1/public/call-sheets/{big}"),
                        ("next-day", f"/api/v1/public/crew/{token}/next")):
        req = urllib.request.Request(api_url + path, headers={"Authorization": f"Bearer {E2E_TOKEN}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            sizes[label] = len(r.read())

    _connect(page, frontend_url, api_url)
    _throttle(page)
    times = {}
    times["days list (30 days)"] = _timed(page, f"{frontend_url}/editor.html#/p/{pid}", "#days li", lambda: expect(page.locator("#days li")).to_have_count(30, timeout=30_000))
    times["day screen (60 scenes)"] = _timed(page, f"{frontend_url}/editor.html#/p/{pid}/day/{big}", "#items .item", lambda: expect(page.locator("#items .item")).to_have_count(n_big, timeout=30_000))
    times["crew tab (60 people)"] = _timed(page, f"{frontend_url}/editor.html#/p/{pid}/crew", "#crew li", lambda: expect(page.locator("#crew li")).to_have_count(60, timeout=30_000))
    times["personal calls picker"] = _timed(page, f"{frontend_url}/editor.html#/p/{pid}/day/{big}", "#addPersonalCall")

    crew_page = page.context.new_page()
    _throttle(crew_page)
    sheet_url = f"{frontend_url}/?sheet={big}&api={api_url}&me={token}"
    times["public sheet, first open (60 scenes, throttled)"] = _timed(crew_page, sheet_url, "#sheet.visible", lambda: expect(crew_page.locator("#scheduleBody tr")).to_have_count(n_big, timeout=30_000))
    times["public sheet, second open (service worker warm)"] = _timed(crew_page, sheet_url, "#sheet.visible")
    stable_url = f"{frontend_url}/?api={api_url}&me={token}"
    times["stable link → next day (30 days listed)"] = _timed(crew_page, stable_url, "#otherDays .day")

    print("\n--- FR-52 pilot scale, iPhone width, throttled 4G (4 Mbit/s, 150 ms) ---")
    for k, v in times.items():
        print(f"  {k:<52} {v:>6.2f} s")
    print("  API response sizes:")
    for k, v in sizes.items():
        print(f"    {k:<20} {v / 1024:>7.1f} KB")
    assert times["public sheet, first open (60 scenes, throttled)"] < 2.0, "the crew's sheet must open under 2 s on throttled 4G"
    for k, v in times.items():
        assert v < 6.0, f"{k} took {v}s"

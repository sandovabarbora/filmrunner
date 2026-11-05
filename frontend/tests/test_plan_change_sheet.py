"""FR-209: what a person sees on a phone the moment the plan changes."""
import json
import urllib.request
import uuid

from conftest import E2E_TOKEN
from playwright.sync_api import Page, expect


def _api(api_url: str, method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(f"{api_url}/api/v1{path}", method=method, data=json.dumps(body).encode() if body is not None else None)
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {E2E_TOKEN}")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def _changed_day(api_url: str) -> tuple[str, str]:
    production = _api(api_url, "POST", "/productions", {"name": f"Plan change {uuid.uuid4().hex[:6]}"})["id"]
    river = _api(api_url, "POST", f"/productions/{production}/locations", {"name": "River bank", "address": "Bank 1"})
    hall = _api(api_url, "POST", f"/productions/{production}/locations", {"name": "Stage 3", "address": "Stage road 3"})
    contact = _api(api_url, "POST", "/contacts", {"name": "Tom Gaffer", "phone": "+420777111222"})
    crew = _api(api_url, "POST", f"/productions/{production}/crew-members", {"contact_id": contact["id"], "department": "Electric", "position": "Gaffer"})

    def scene(order: int, number: str, location: dict) -> dict:
        return {"order_index": order, "scene_number": number, "int_ext": "EXT", "day_night": "DAY", "set_description": "Bank", "location_id": location["id"], "page_count_eighths": 8}

    def revision(call: str, scenes: list[dict], safety: str | None = None) -> dict:
        return {"general_crew_call": call, "safety_notes": safety, "schedule_items": scenes, "crew_calls": []}

    day = _api(api_url, "POST", f"/productions/{production}/call-sheets", {"shoot_date": "2031-03-04", "day_number": 1, "day_count": 2, "unit_name": "Main", "initial_revision": revision("07:00", [scene(1, "42", river), scene(2, "43", river)])})
    _api(api_url, "POST", f"/call-sheets/{day['id']}/revisions", revision("06:30", [scene(1, "42", hall)], safety="Wet floor."))
    return day["id"], crew["personal_token"]


def test_a_changed_call_answers_when_where_and_what_to_do_on_the_first_screen(page: Page, frontend_url: str, api_url: str) -> None:
    sheet, token = _changed_day(api_url)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{frontend_url}/?sheet={sheet}&api={api_url}&me={token}")
    page.wait_for_selector("#confirmBtn", timeout=15_000)

    expect(page.locator("#yourPlace")).to_contain_text("Stage 3")
    expect(page.locator("#yourPlaceWas")).to_contain_text("River bank")
    box = page.locator("#confirmBtn").bounding_box()
    assert box is not None and box["y"] + box["height"] <= 844
    assert page.locator(".rev-mark").count() == 0

    # The place is already on the card, and the crew call is someone else's time now: both wait behind one tap.
    expect(page.locator("#revChanges li[data-field='safety_notes']")).to_be_visible()
    expect(page.locator("#revChanges li[data-field='location']")).to_have_count(0)
    expect(page.locator("#revMore li[data-field='crew_call']")).to_be_hidden()
    page.click("#revMoreToggle")
    expect(page.locator("#revMore li[data-field='crew_call']")).to_be_visible()
    expect(page.locator("#revMore li[data-field='scenes_removed']")).to_have_text("Scene 43 dropped")

    # Whoever already confirmed came back for a time, not for this list.
    page.click("#confirmBtn")
    page.wait_for_selector("#confirmDone", timeout=15_000)
    page.reload()
    page.wait_for_selector("#confirmDone", timeout=15_000)
    expect(page.locator("#revChanges")).to_have_count(0)
    expect(page.locator("#revMoreToggle")).to_contain_text("What changed")
    expect(page.locator("#revMore")).to_be_hidden()

    # Paper has no tap: a printed sheet carries every change.
    page.emulate_media(media="print")
    expect(page.locator("#revMore li[data-field='crew_call']")).to_be_visible()
    expect(page.locator("#revMoreToggle")).to_be_hidden()


def test_the_shared_link_folds_nothing(page: Page, frontend_url: str, api_url: str) -> None:
    sheet, _ = _changed_day(api_url)
    page.goto(f"{frontend_url}/?sheet={sheet}&api={api_url}")
    page.wait_for_selector("#revChanges", timeout=15_000)
    expect(page.locator("#revChanges li[data-field='crew_call']")).to_be_visible()
    expect(page.locator("#revChanges li[data-field='location']")).to_be_visible()
    expect(page.locator("#revMoreToggle")).to_have_count(0)
    expect(page.locator("#you")).to_have_count(0)

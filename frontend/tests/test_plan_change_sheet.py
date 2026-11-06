"""FR-209: what a person sees on a phone the moment the plan changes."""
import json
import urllib.request
import uuid
from datetime import date

import pytest
from conftest import E2E_TOKEN
from playwright.sync_api import Page, expect


def _api(api_url: str, method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(f"{api_url}/api/v1{path}", method=method, data=json.dumps(body).encode() if body is not None else None)
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {E2E_TOKEN}")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def _changed_day(api_url: str, days_ahead: int | None = None) -> tuple[str, str]:
    production = _api(api_url, "POST", "/productions", {"name": f"Plan change {uuid.uuid4().hex[:6]}"})["id"]
    river = _api(api_url, "POST", f"/productions/{production}/locations", {"name": "River bank", "address": "Bank 1"})
    hall = _api(api_url, "POST", f"/productions/{production}/locations", {"name": "Stage 3", "address": "Stage road 3"})
    contact = _api(api_url, "POST", "/contacts", {"name": "Tom Gaffer", "phone": "+420777111222"})
    crew = _api(api_url, "POST", f"/productions/{production}/crew-members", {"contact_id": contact["id"], "department": "Electric", "position": "Gaffer"})

    def scene(order: int, number: str, location: dict) -> dict:
        return {"order_index": order, "scene_number": number, "int_ext": "EXT", "day_night": "DAY", "set_description": "Bank", "location_id": location["id"], "page_count_eighths": 8}

    def revision(call: str, scenes: list[dict], safety: str | None = None) -> dict:
        return {"general_crew_call": call, "safety_notes": safety, "schedule_items": scenes, "crew_calls": []}

    day = _api(api_url, "POST", f"/productions/{production}/call-sheets", {"shoot_date": date.today().isoformat() if days_ahead == 0 else "2031-03-04", "day_number": 1, "day_count": 2, "unit_name": "Main", "initial_revision": revision("07:00", [scene(1, "42", river), scene(2, "43", river)])})
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


def test_signing_in_opens_on_what_needs_you_and_leads_to_the_day(page: Page, frontend_url: str, api_url: str) -> None:
    sheet, _ = _changed_day(api_url, days_ahead=0)
    name = _api(api_url, "GET", f"/call-sheets/{sheet}")["production_title"]
    connection = json.dumps({"apiBase": api_url, "token": E2E_TOKEN})
    page.add_init_script(f"localStorage.setItem('filmrunner.editor.connection', {json.dumps(connection)});")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{frontend_url}/editor.html")

    item = page.locator("#dashItems .dash-item", has_text=name)
    expect(item).to_contain_text("1 person has not confirmed", timeout=15_000)
    expect(item).to_contain_text("0 of 1 confirmed")
    expect(item).to_contain_text("REV B")
    expect(item).to_contain_text("today 06:30")
    assert int(page.locator("#dashCount").inner_text()) >= 1
    expect(page.locator("#productions")).to_contain_text(name)  # every film stays one tap away

    item.click()
    expect(page.locator("#seenPanel")).to_contain_text("REV B", timeout=15_000)


def _send_the_built_in_api_to_the_test_server(page: Page, api_url: str) -> None:
    """The test environment always talks to the deployed API; here that address must reach the local one."""
    allow = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}

    def forward(route) -> None:
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers=allow)
            return
        response = route.fetch(url=route.request.url.replace("https://filmrunner-api.fly.dev", api_url))
        route.fulfill(response=response, headers={**response.headers, **allow})

    page.route("https://filmrunner-api.fly.dev/**", forward)


def _tap_logo(page: Page, selector: str, times: int) -> None:
    for _ in range(times):
        page.click(selector, no_wait_after=True)


def test_seven_taps_open_personas_and_each_one_sees_their_own_app(page: Page, frontend_url: str, api_url: str) -> None:
    _send_the_built_in_api_to_the_test_server(page, api_url)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#logo", timeout=10_000)
    _tap_logo(page, "#logo", 7)
    expect(page.locator("#testLab")).to_be_visible(timeout=10_000)
    expect(page.locator("#adminScreen")).to_have_count(0)  # seven taps do not stop at five

    page.click("#testPersonas [data-persona='produkcni']", timeout=15_000)
    expect(page.locator("#dashCount")).to_have_text("2", timeout=15_000)
    expect(page.locator("#sandboxBar")).to_contain_text("Production manager")
    expect(page.locator("#productions")).to_contain_text("Nádraží")

    page.click("#sandboxSwitch")
    page.click("#testPersonas [data-persona='ad']", timeout=15_000)
    expect(page.locator("#sandboxBar")).to_contain_text("1st AD", timeout=15_000)
    expect(page.locator("#productions li")).to_have_count(1)

    page.click("#sandboxSwitch")
    page.click("#testPersonas [data-persona='gaffer']", timeout=15_000)
    expect(page.locator("#yourCall")).to_have_text("05:00", timeout=15_000)
    expect(page.locator("#sandboxBar")).to_contain_text("Gaffer")
    assert page.locator("#confirmBtn").count() == 1

    # Leaving ends the persona: no test sign-in survives into the real app.
    page.click("#sandboxExit")
    page.wait_for_selector("#openEditor", timeout=10_000)
    assert page.evaluate("localStorage.getItem('filmrunner.sandbox')") is None
    assert page.evaluate("localStorage.getItem('filmrunner.editor.connection')") is None
    page.unroute_all(behavior="ignoreErrors")


def test_seven_taps_work_from_the_home_screen_too(page: Page, frontend_url: str, api_url: str) -> None:
    _send_the_built_in_api_to_the_test_server(page, api_url)
    page.goto(f"{frontend_url}/")
    page.wait_for_selector("#openDemo", timeout=10_000)
    _tap_logo(page, ".masthead h1", 7)
    expect(page.locator("#testLab")).to_be_visible(timeout=10_000)
    page.unroute_all(behavior="ignoreErrors")


def test_a_real_session_shows_no_test_bar(page: Page, frontend_url: str, api_url: str) -> None:
    connection = json.dumps({"apiBase": api_url, "token": E2E_TOKEN})
    page.add_init_script(f"localStorage.setItem('filmrunner.editor.connection', {json.dumps(connection)});")
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#createProduction", timeout=15_000)
    expect(page.locator("#sandboxBar")).to_have_count(0)


@pytest.mark.keeps_folds
def test_the_day_screen_is_about_changing_the_plan(page: Page, frontend_url: str, api_url: str) -> None:
    """Publish stays in reach, and everything a changed plan does not need waits behind one tap."""
    sheet, _ = _changed_day(api_url)
    production = _api(api_url, "GET", f"/call-sheets/{sheet}")["production_id"]
    connection = json.dumps({"apiBase": api_url, "token": E2E_TOKEN})
    page.add_init_script(f"localStorage.setItem('filmrunner.editor.connection', {json.dumps(connection)});")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{frontend_url}/editor.html#/p/{production}/day/{sheet}")
    page.wait_for_selector("#publish", timeout=15_000)

    box = page.locator("#publish").bounding_box()
    assert box is not None and box["y"] + box["height"] <= 844
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight / 2)")
    box = page.locator("#publish").bounding_box()
    assert box is not None and box["y"] + box["height"] <= 844

    expect(page.locator("#shareLink")).to_be_hidden()
    expect(page.locator("#personalLinks ul")).to_be_hidden()
    expect(page.locator("#cancelDayBtn")).to_be_hidden()
    expect(page.locator("#unconfirmed")).to_be_hidden()
    expect(page.locator("#confirmedCount")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollHeight") < 3000
    page.click("#shareDetails summary")
    expect(page.locator("#shareLink")).to_be_visible()


@pytest.mark.parametrize("target", [".masthead h1", ".home-mark"])
def test_unhurried_taps_on_either_name_open_the_test_environment(page: Page, frontend_url: str, api_url: str, target: str) -> None:
    _send_the_built_in_api_to_the_test_server(page, api_url)
    page.goto(f"{frontend_url}/")
    page.wait_for_selector("#openDemo", timeout=10_000)
    for _ in range(7):
        page.click(target, no_wait_after=True)
        page.wait_for_timeout(700)
    expect(page.locator("#testLab")).to_be_visible(timeout=10_000)
    page.unroute_all(behavior="ignoreErrors")


def test_unhurried_taps_in_the_editor_do_not_stop_at_admin(page: Page, frontend_url: str, api_url: str) -> None:
    _send_the_built_in_api_to_the_test_server(page, api_url)
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#logo", timeout=10_000)
    for _ in range(7):
        page.click("#logo", no_wait_after=True)
        page.wait_for_timeout(700)
    expect(page.locator("#testLab")).to_be_visible(timeout=10_000)
    expect(page.locator("#adminScreen")).to_have_count(0)
    page.unroute_all(behavior="ignoreErrors")


def test_nothing_runs_behind_what_a_crew_member_reads(page: Page, frontend_url: str, api_url: str) -> None:
    sheet, token = _changed_day(api_url)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{frontend_url}/?sheet={sheet}&api={api_url}&me={token}")
    page.wait_for_selector("#confirmBtn", timeout=15_000)
    expect(page.locator(".hero-bg")).to_have_count(0)
    expect(page.locator(".frame img")).to_be_visible()
    expect(page.locator("#confirmAsk")).to_contain_text("The plan changed")
    box = page.locator("#confirmBtn").bounding_box()
    assert box is not None and box["y"] + box["height"] <= 844

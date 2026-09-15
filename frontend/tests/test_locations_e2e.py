"""End-to-end: the Locations tab and a scene's location picker (FR-19),
against the real API — same harness as test_editor_e2e.py.

The geocoder call genuinely goes out over the network (Nominatim), like
every other external call this suite makes to the real subprocess API and
a real Postgres. Where CI has open egress, a real address genuinely
resolves; a nonsense one genuinely doesn't. Both branches are exercised
for real rather than through a mock — the dod's own failure case (a miss
must stay visible, never silently trusted) included.
"""

import uuid

from playwright.sync_api import Page, expect

from test_editor_e2e import _connect, _create_production


def test_add_location_with_real_address_shows_resolved_place_name(page: Page, frontend_url: str, api_url: str) -> None:
    """dod: "the editor shows the resolved place name next to the address
    so the AD can catch it" — a Czech street name can resolve to the wrong
    place, so the resolution itself must be visible, not just trusted."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E loc {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Locations']")
    page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Riverbank, Troja")
    page.fill("#locAddress", "Trojská 1, Praha 7")
    page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("Riverbank, Troja", timeout=15_000)
    expect(page.locator("#locations")).to_contain_text("resolved:")


def test_add_location_with_unresolvable_address_stays_editable_and_visible(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (dod): a geocoder miss never blocks saving the location,
    and the editor makes the miss visible rather than silent."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E loc-miss {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Locations']")
    page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Nowhere")
    page.fill("#locAddress", "zzqzzq nonexistent street 000000, nowhereville")
    page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("Nowhere", timeout=15_000)
    expect(page.locator("#locations")).to_contain_text("not resolved")


def test_scene_can_pick_a_location_and_publish_still_succeeds(page: Page, frontend_url: str, api_url: str) -> None:
    """Connect-first (TEAM.md): a location is reachable from a scene, not
    only from its own tab. Publishing with a located scene but no resolved
    coordinates must not fail or hang (weather/sunrise stay empty)."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E loc2 {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Locations']")
    page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Studio A")
    page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("Studio A", timeout=15_000)

    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("1")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("INT. STUDIO A")
    page.locator("#items .item").nth(0).get_by_label("Location").select_option(label="Studio A")

    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)


def test_suggest_weather_without_resolved_location_warns_instead_of_hanging(page: Page, frontend_url: str, api_url: str) -> None:
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E loc3 {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.click("text=Suggest weather")
    expect(page.locator("#notice")).to_contain_text("Pick a location", timeout=15_000)

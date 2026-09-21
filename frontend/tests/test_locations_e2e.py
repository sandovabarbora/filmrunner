"""End-to-end: the Locations tab and a scene's location picker (FR-19),
against the real API — same harness as test_editor_e2e.py.

The geocoder call genuinely goes out over the network (Nominatim), like
every other external call this suite makes to the real subprocess API and
a real Postgres. Where CI has open egress, a real address genuinely
resolves; a nonsense one genuinely doesn't. Both branches are exercised
for real rather than through a mock — the dod's own failure case (a miss
must stay visible, never silently trusted) included.
"""

import re
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

    # FR-35: on the sheet, a resolved location gets a maps link on its address and parking under it.
    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("4")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("EXT. RIVERBANK")
    page.locator("#items .item").nth(0).get_by_label("Location").select_option(label="Riverbank, Troja")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#shareLink", timeout=10_000)
    v = page.context.new_page(); v.goto(page.locator("#shareLink").get_attribute("href")); v.wait_for_selector("#locations", timeout=15_000)
    link = v.locator("#locations .address a")
    expect(link).to_have_text("Trojská 1, Praha 7")
    assert link.get_attribute("href").startswith("https://maps.google.com/?q=50.")
    v.close()


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

    # FR-35: the crew's sheet says where — the location by name on the scene and in a "Where" block with parking.
    page.wait_for_selector("#shareLink", timeout=10_000)
    v = page.context.new_page(); v.goto(page.locator("#shareLink").get_attribute("href")); v.wait_for_selector("#locations", timeout=15_000)
    block = v.locator("#locations .location")
    expect(block).to_have_count(1)
    expect(block).to_contain_text("Studio A")
    expect(block).to_contain_text("Sc 1")
    expect(v.locator("#scheduleBody .set").first).to_contain_text("Studio A")
    assert v.locator("#locations a").count() == 0  # no address, no coordinates: no maps link to a wrong place
    v.close()


def test_suggest_weather_without_resolved_location_warns_instead_of_hanging(page: Page, frontend_url: str, api_url: str) -> None:
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E loc3 {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.click("text=Suggest weather")
    expect(page.locator("#notice")).to_contain_text("Pick a location", timeout=15_000)


def test_day_without_location_says_what_is_missing_and_picking_one_fills_sunrise(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-27: the sunrise hint names what a location would give and links to Locations; once a
    scene gets a resolved location, sunrise fills without a reload. Real Nominatim, as above."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E sun {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    hint = page.locator("#sunHint")
    expect(hint).to_have_attribute("data-state", "none")
    expect(hint).to_contain_text("Add a location to this day to get sunrise, sunset, weather and the nearest hospital")
    assert hint.get_by_role("link", name="Locations").get_attribute("href").endswith("/locations")

    hint.get_by_role("link", name="Locations").click()  # the hint's own link takes the AD to the Locations tab
    page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Old Town Square"); page.fill("#locAddress", "Staroměstské náměstí, Praha 1")
    page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("resolved:", timeout=15_000)

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    expect(page.locator("#sunHint")).to_contain_text("Pick a location on a scene below")
    assert page.locator("#sunrise").input_value() == ""
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Location").select_option(label="Old Town Square")
    expect(page.locator("#sunrise")).to_have_value(re.compile(r"^\d{2}:\d{2}$"), timeout=10_000)
    expect(page.locator("#sunset")).to_have_value(re.compile(r"^\d{2}:\d{2}$"))
    expect(page.locator("#sunHint")).to_have_attribute("data-state", "filled")


def test_sun_lookup_failure_tells_the_ad_to_type_the_times(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (dod): when the suggestion cannot be fetched the hint says so, instead of still asking for a location."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E sunfail {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Locations']")
    page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Studio B"); page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("Studio B", timeout=15_000)

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.route(f"{api_url}/**/sun?*", lambda route: route.abort())
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Location").select_option(label="Studio B")
    expect(page.locator("#sunHint")).to_have_attribute("data-state", "failed", timeout=10_000)
    expect(page.locator("#sunHint")).to_contain_text("Could not fetch suggestions")


def test_deleting_a_location_drops_it_from_a_published_scene_without_breaking_the_day(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-38: removing a location a scene already used keeps the scene's text
    and just loses the link; the day's FR-27 hint reappears rather than
    showing a blank sunrise with no explanation (the dod's failure case)."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E loc-del {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Locations']")
    page.wait_for_selector("#locName", timeout=10_000)
    page.fill("#locName", "Studio C")
    page.click("#addLocation")
    expect(page.locator("#locations")).to_contain_text("Studio C", timeout=15_000)

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("1")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("INT. STUDIO C")
    page.locator("#items .item").nth(0).get_by_label("Location").select_option(label="Studio C")
    expect(page.locator("#sunHint")).to_have_attribute("data-state", "no-coords", timeout=15_000)
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)

    # Get to Locations via the sunrise hint's own link (a published day has no top-level tabs of its own).
    page.locator("#sunHint").get_by_role("link", name="Locations").click()
    page.wait_for_selector("#locName", timeout=10_000)
    page.once("dialog", lambda d: d.accept())
    page.click("#locations >> role=button[name='Remove Studio C']")
    expect(page.locator("#notice")).to_contain_text("Studio C removed", timeout=15_000)
    expect(page.get_by_text("No locations yet.")).to_be_visible()

    # Reopening the published day: the scene still loads and can publish again,
    # its location select is back to "no location", and the sunrise hint returns.
    page.click("role=tab[name='Days']")
    page.locator("#days a.row").first.click()
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    expect(page.locator("#items .item").nth(0).get_by_label("Set")).to_have_value("INT. STUDIO C")
    expect(page.locator("#items .item").nth(0).get_by_label("Location")).to_have_value("")
    expect(page.locator("#sunHint")).to_have_attribute("data-state", "none")
    expect(page.locator("#sunHint")).to_contain_text("Add a location to this day to get sunrise, sunset, weather and the nearest hospital")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)

"""FR-141 dod: every route the frontend's own router declares (`frontend/src/editor/route.ts`)
must be reachable by following only clickable links and buttons, starting from the entry
page — never a direct `goto()` into an inner route. TEAM.md's product rule ("connect first,
then add") says a route reachable only by typing its URL is not done; this sweep is the
automatic check for that, across the sheet -> editor -> production -> day -> crew-link ->
viewer chain.

The one `goto()` this test does perform, besides the entry page itself, injects the editor's
connection into `localStorage` before any navigation — the same bypass every other e2e test
in this suite uses, standing in for a sign-in UI this build has no way to drive without a
real Supabase project. That is not a route of the app; it is how this harness authenticates.
"""

import re
import uuid

from playwright.sync_api import Page, expect

from conftest import E2E_TOKEN

# The full set of (screen, tab) combinations `route.ts`'s `Route` type declares.
DECLARED_ROUTES = {
    ("productions", None),
    ("production", "days"),
    ("production", "crew"),
    ("production", "cast"),
    ("production", "locations"),
    ("production", "members"),
    ("production", "settings"),
    ("day", None),
}


def _classify_hash(hash_value: str) -> tuple[str, str | None]:
    """Mirrors `parseRoute` in `route.ts` — kept independent of the app bundle so this
    test is checking the router's observable behaviour, not re-running its own code."""
    parts = [p for p in re.sub(r"^#/?", "", hash_value).split("/") if p]
    if parts and parts[0] == "p" and len(parts) > 1:
        if len(parts) > 2 and parts[2] == "day":
            return ("day", None)
        tab = parts[2] if len(parts) > 2 and parts[2] in {"crew", "cast", "locations", "members", "settings"} else "days"
        return ("production", tab)
    return ("productions", None)


def test_every_declared_route_reachable_from_entry_page_by_clicks_only(
    page: Page, frontend_url: str, api_url: str
) -> None:
    visited: set[tuple[str, str | None]] = set()

    def record() -> None:
        visited.add(_classify_hash(page.evaluate("location.hash")))

    page.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )

    # Entry page: the public call sheet. #openDemo and #openEditor are real <a href> links.
    page.goto(f"{frontend_url}/index.html")
    page.wait_for_selector("#openDemo", timeout=10_000)
    page.click("#openDemo")
    page.wait_for_selector("#sheet.visible", timeout=10_000)

    page.go_back()
    page.wait_for_selector("#openEditor", timeout=10_000)
    page.click("#openEditor")
    page.wait_for_selector("#newProduction", timeout=10_000)
    record()  # productions

    production = f"Reach {uuid.uuid4().hex[:6]}"
    page.fill("#newProduction", production)
    page.click("#createProduction")
    page.wait_for_selector("#newDay", timeout=10_000)
    record()  # production/days

    for tab, selector in (
        ("Crew", "#crewName"),
        ("Cast", "#castName"),
        ("Locations", "#locName"),
        ("Members", "#memberEmail"),
        ("Settings", "#productionName"),
        ("Days", "#newDay"),
    ):
        tab_link = page.locator(f"role=tab[name='{tab}']")
        if tab_link.count() == 0:
            continue  # not every tab is visible to every role; the final assertion names anything this leaves unreached
        tab_link.click()
        page.wait_for_selector(selector, timeout=10_000)
        record()

    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    record()  # day/new

    page.fill("#shoot_date", "2026-11-02")
    page.fill("#day_number", "1")
    page.fill("#day_count", "1")
    page.fill("#general_crew_call", "06:00")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("1")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("STAGE")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    record()  # day/<real id>

    # Breadcrumb back to Productions — a real click, not a goto() — then back in via its own row.
    page.click("role=link[name='Productions']")
    page.wait_for_selector("#productions", timeout=10_000)
    record()
    page.click(f"#productions >> text={production}")
    page.wait_for_selector("#days", timeout=10_000)
    record()

    # Reopen the published day itself (the days list is a different screen from the day it links to).
    page.locator("#days a.row").first.click()
    page.wait_for_selector("#shareLink", timeout=10_000)
    record()

    # Crew link: opens in a new tab (target="_blank"), a real click on #shareLink — the "viewer" leg.
    with page.context.expect_page() as new_page_info:
        page.click("#shareLink")
    viewer = new_page_info.value
    viewer.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 1 of 1" in viewer.locator("#dayLabel").inner_text()
    viewer.close()

    missing = DECLARED_ROUTES - visited
    assert not missing, (
        f"route.ts declares these routes but the sweep never reached them by following a "
        f"link or button from the entry page: {sorted(missing, key=str)}"
    )

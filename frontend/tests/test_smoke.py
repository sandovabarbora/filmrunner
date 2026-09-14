"""Smoke test for the offline-first call sheet PWA.

Serves the built app (frontend/dist, run `npm run build` first) over a
local static server and checks the shell renders, the service worker
registers, and the URL modes behave. Data loading against the API is
covered by the backend tests; this guards the app shell that must work
with no signal on set.
"""

from pathlib import Path

from playwright.sync_api import Page

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"


def test_root_is_the_entry_page_not_a_form(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    page.wait_for_selector("#openEditor", timeout=10_000)
    assert "FilmRunner" in (page.locator("h1").text_content() or "")
    assert page.locator("#lookup").count() == 0
    assert page.locator("#openEditor").get_attribute("href") == "editor.html"
    page.click("#openDemo")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 7 of 24" in page.locator("#dayLabel").inner_text()


def test_dev_mode_shows_the_lookup_form(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html?dev=1")
    page.wait_for_selector("#loadBtn", timeout=10_000)
    assert page.locator("#loadBtn").is_visible()
    assert not page.locator("#sheet").evaluate("el => el.classList.contains('visible')")


def test_share_link_loads_from_api_without_form(page: Page, frontend_url: str) -> None:
    page.route(
        "**/api/v1/public/call-sheets/abc",
        lambda route: route.fulfill(
            content_type="application/json",
            body='{"unit_name":"Second Unit","day_number":3,"day_count":9,"shoot_date":"2026-10-01",'
            '"current_revision":{"revision_letter":"A","schedule_items":[]}}',
        ),
    )
    page.goto(f"{frontend_url}/index.html?sheet=abc&api=http://api.test")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 3 of 9" in page.locator("#dayLabel").inner_text()
    assert page.locator("#lookup").count() == 0


def test_service_worker_registers(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    registered = page.evaluate(
        "navigator.serviceWorker.ready.then(r => Boolean(r.active || r.installing || r.waiting))"
    )
    assert registered is True


def test_load_without_api_shows_offline_status(page: Page, frontend_url: str) -> None:
    """Failure case: no API and no cache must show a visible status, not a blank sheet."""
    page.goto(f"{frontend_url}/index.html?dev=1")
    page.fill("#apiBase", "http://127.0.0.1:1")
    page.fill("#callSheetId", "00000000-0000-0000-0000-000000000000")
    page.click("#loadBtn")
    page.wait_for_function(
        "document.querySelector('#status').textContent.trim().length > 0", timeout=10_000
    )
    assert page.locator("#status").inner_text().strip() != ""


def test_demo_mode_renders_bundled_call_sheet(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 7 of 24" in page.locator("#dayLabel").inner_text()
    assert page.locator("#scheduleBody tr").count() == 4
    assert page.locator("#revBadgeWrap").inner_text().strip() == "REV B"
    assert page.locator("#lookup").count() == 0


def test_demo_mode_missing_json_shows_error_not_blank(page: Page, frontend_url: str) -> None:
    """Failure case: if the bundled JSON is unreachable and nothing is cached, say so."""
    page.route("**/demo/call-sheet.json", lambda route: route.abort())
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_function("document.querySelector('#status').textContent.trim().length > 0", timeout=10_000)
    assert "error" in page.locator("#status").get_attribute("class")
    assert not page.locator("#sheet").evaluate("el => el.classList.contains('visible')")


def test_schedule_text_is_not_interpreted_as_html(page: Page, frontend_url: str) -> None:
    """Security: a set note containing markup must render as text (FR-7 finding 2)."""
    page.route(
        "**/demo/call-sheet.json",
        lambda route: route.fulfill(
            content_type="application/json",
            body='{"unit_name":"U","day_number":1,"day_count":1,"shoot_date":"2026-01-01",'
            '"current_revision":{"revision_letter":"A","schedule_items":[{"order_index":1,'
            '"scene_number":"1","int_ext":"INT","day_night":"DAY",'
            '"set_description":"<img src=x onerror=window.__pwned=1>","page_count_eighths":8}]}}',
        ),
    )
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert page.locator("#scheduleBody img").count() == 0
    assert "<img" in page.locator("#scheduleBody").inner_text()
    assert page.evaluate("window.__pwned") is None


def test_contacts_render_with_tap_to_call_and_no_number_fallback(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#contacts", timeout=10_000)
    assert "Eva Dvořáková" in page.locator("#contacts .hod").inner_text()
    tel_links = page.locator("#contacts a.phone")
    assert tel_links.count() >= 5
    assert tel_links.first.get_attribute("href").startswith("tel:+420")
    assert page.locator("#contacts .phone.none").count() == 1  # UPM has no number on file
    assert "Bulovka" in page.locator("#contacts .hospital").inner_text()


_SHEET_BODY = (
    '{"unit_name":"Second Unit","day_number":3,"day_count":9,"shoot_date":"2026-10-01",'
    '"current_revision":{"revision_letter":"A","schedule_items":[]}}'
)


def test_going_offline_after_a_live_load_shows_cached_status_with_timestamp(page: Page, frontend_url: str) -> None:
    """FR-9: the service worker's own cache can answer fetch() when offline,
    which used to read as "Live data". The worker now stamps every response
    with where it came from (vite.config.ts); loader.ts trusts the stamp,
    not whether fetch() merely succeeded.
    """
    page.route(
        "**/api/v1/public/call-sheets/xyz",
        lambda route: route.fulfill(content_type="application/json", body=_SHEET_BODY),
    )
    url = f"{frontend_url}/index.html?sheet=xyz&api=http://api.test"
    page.goto(url)
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert page.locator("#status").get_attribute("class") == "status online"

    # Give the worker's own cache.put() (fired after fetchDidSucceed) a beat
    # to land before we cut the network it would otherwise fall back to.
    page.wait_for_function(
        "caches.open('filmrunner-api-v1').then(c => c.keys()).then(k => k.length > 0)",
        timeout=10_000,
    )

    # Simulate the network being down for this call specifically (not the
    # whole page — the local test server standing in for "no signal on
    # set" would otherwise fail the navigation itself, which isn't what
    # this test is about; the app shell's own offline navigation is served
    # by the precache route, unrelated to this API-freshness check).
    page.unroute("**/api/v1/public/call-sheets/xyz")
    page.route("**/api/v1/public/call-sheets/xyz", lambda route: route.abort())

    page.goto(url)
    page.wait_for_function(
        "document.querySelector('#status').textContent.trim().length > 0", timeout=10_000
    )
    status = page.locator("#status")
    assert status.get_attribute("class") == "status offline"
    assert "Offline" in status.inner_text()
    assert "saved" in status.inner_text()
    assert "Day 3 of 9" in page.locator("#dayLabel").inner_text()


def test_worker_without_the_freshness_stamp_shows_unknown_not_live(page: Page, frontend_url: str) -> None:
    """Failure case: an older service worker (deployed before this stamp
    existed) can still be the one controlling the page after an upgrade,
    since it keeps intercepting fetches until it is replaced. It cannot
    tell live from cached either, so the app must not guess "Live" just
    because fetch() succeeded.

    A fetch a service worker intercepts and re-issues isn't reliably
    routable at the network layer across Playwright versions (registration
    itself and in-worker fetches are separate browser targets from the
    page), so this test avoids interception entirely: it swaps the built
    sw.js on disk for a stub that never stamps, and serves the call sheet
    itself as a same-origin static file the local server (conftest.py)
    answers directly — a real round trip, nothing mocked.
    """
    sw_path = DIST_DIR / "sw.js"
    original_sw = sw_path.read_text()
    stale_sw = (
        "self.addEventListener('install', () => self.skipWaiting());"
        "self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));"
        "self.addEventListener('fetch', (e) => {"
        "  if (e.request.url.includes('/api/v1/public/call-sheets/')) e.respondWith(fetch(e.request));"
        "});"
    )
    sw_path.write_text(stale_sw)

    fixture_path = DIST_DIR / "api" / "v1" / "public" / "call-sheets" / "xyz"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(_SHEET_BODY)

    try:
        page.goto(f"{frontend_url}/index.html?dev=1")
        page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=10_000)

        page.fill("#apiBase", frontend_url)
        page.fill("#callSheetId", "xyz")
        page.click("#loadBtn")

        page.wait_for_selector("#sheet.visible", timeout=10_000)
        status = page.locator("#status")
        assert "Unknown freshness" in status.inner_text()
        assert "Live" not in status.inner_text()
    finally:
        sw_path.write_text(original_sw)
        fixture_path.unlink()

"""Smoke test for the offline-first call sheet PWA.

Serves the built app (frontend/dist, run `npm run build` first) over a
local static server and checks the shell renders, the service worker
registers, and the URL modes behave. Data loading against the API is
covered by the backend tests; this guards the app shell that must work
with no signal on set.
"""

import http.server
import socketserver
import threading
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest
from playwright.sync_api import Page

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"


@pytest.fixture(scope="session")
def frontend_url() -> Iterator[str]:
    assert (DIST_DIR / "index.html").exists(), "run `npm run build` in frontend/ first"
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST_DIR))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()


def test_root_shows_demo_not_a_form(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "FilmRunner" in (page.locator("h1").text_content() or "")
    assert page.locator("#lookup").count() == 0
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

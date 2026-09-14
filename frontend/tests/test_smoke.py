"""Smoke test for the offline-first call sheet PWA.

Serves frontend/ over a local static server and checks the shell renders
and the service worker registers. Data loading against the API is covered
by the backend tests; this guards the app shell that must work with no
signal on set.
"""

import http.server
import socketserver
import threading
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest
from playwright.sync_api import Page

FRONTEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def frontend_url() -> Iterator[str]:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(FRONTEND_DIR))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()


def test_shell_renders(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    assert "call sheet viewer" in page.locator("h1").inner_text()
    assert page.locator("#loadBtn").is_visible()


def test_service_worker_registers(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    registered = page.evaluate(
        "navigator.serviceWorker.ready.then(r => Boolean(r.active || r.installing || r.waiting))"
    )
    assert registered is True


def test_load_without_api_shows_offline_status(page: Page, frontend_url: str) -> None:
    """Failure case: no API and no cache must show a visible status, not a blank sheet."""
    page.goto(f"{frontend_url}/index.html")
    page.fill("#apiBase", "http://127.0.0.1:1")
    page.fill("#callSheetId", "00000000-0000-0000-0000-000000000000")
    page.click("#loadBtn")
    page.wait_for_function(
        "document.querySelector('#status').textContent.trim().length > 0", timeout=10_000
    )
    assert page.locator("#status").inner_text().strip() != ""

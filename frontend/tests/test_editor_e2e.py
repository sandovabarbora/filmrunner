"""End-to-end: the AD editor against the real API (FR-10 dod).

Starts uvicorn on the test database (same URL the backend tests use),
serves the built frontend, and drives the editor like an AD on a phone:
connect, create a production, fill a day, publish A, change the crew
call, publish B, open the crew link and see REV B.
"""

import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
TEST_DB_URL = os.environ.get(
    "FILMRUNNER_DATABASE_URL",
    "postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner_test",
)
E2E_TOKEN = "e2e-token"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def api_url() -> Iterator[str]:
    env = {
        **os.environ,
        "FILMRUNNER_DATABASE_URL": TEST_DB_URL,
        "FILMRUNNER_API_BEARER_TOKEN": E2E_TOKEN,
        "FILMRUNNER_ENVIRONMENT": "development",
        "FILMRUNNER_CORS_ORIGINS": "*",
    }
    subprocess.run(
        [sys.executable, "-c", "from app.database import Base, engine; import app.models; Base.metadata.create_all(engine)"],
        cwd=BACKEND_DIR, env=env, check=True,
    )
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    import urllib.request
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        proc.kill()
        raise RuntimeError("API did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def test_ad_publishes_a_then_b_and_crew_sees_b(page: Page, frontend_url: str, api_url: str) -> None:
    production = f"E2E {uuid.uuid4().hex[:6]}"
    page.goto(f"{frontend_url}/editor.html")

    # Connect (temporary shared token, ADR-003 decision 3).
    page.fill("#apiBase", api_url)
    page.fill("#token", E2E_TOKEN)
    page.click("#connect")

    # Production.
    page.wait_for_selector("#newProduction", timeout=10_000)
    page.fill("#newProduction", production)
    page.click("#createProduction")
    page.wait_for_function("document.querySelector('#production') && document.querySelector('#production').value !== ''", timeout=10_000)

    # Day and calls.
    page.fill("#shoot_date", "2026-09-22")
    page.fill("#day_number", "7")
    page.fill("#day_count", "24")
    page.fill("#general_crew_call", "06:30")
    page.fill("#shooting_call", "07:30")
    page.fill("#safety_notes", "Riverbank: life vests within 3 m of the water.")

    # Two scenes.
    page.click("#addScene")
    page.click("#addScene")
    scenes = page.locator("#items .item")
    assert scenes.count() == 2
    scenes.nth(0).get_by_label("Scene").fill("42")
    scenes.nth(0).get_by_label("Set").fill("RIVERBANK, TROJA. Marta finds the boat.")
    scenes.nth(1).get_by_label("Scene").fill("17")
    scenes.nth(1).get_by_label("Set").fill("COTTAGE KITCHEN. Breakfast.")

    # Publish A.
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    share = page.locator("#shareLink").get_attribute("href")
    assert share and "?sheet=" in share and "api=" in share

    # Hot revision: crew call moves, publish B.
    page.fill("#general_crew_call", "07:30")
    expect(page.locator("#publishState")).to_contain_text("Publish to send REV B")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)

    # The crew link shows B with the new call.
    page.goto(share)
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    assert page.locator("#revBadgeWrap").inner_text().strip() == "REV B"
    assert page.locator("#crewCall").inner_text().strip() == "07:30"
    assert page.locator("#scheduleBody tr").count() == 2


def test_publish_without_network_keeps_the_draft(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (FR-10 dod): losing the network must not lose the draft."""
    page.goto(f"{frontend_url}/editor.html")
    page.fill("#apiBase", api_url)
    page.fill("#token", E2E_TOKEN)
    page.click("#connect")
    page.wait_for_selector("#newProduction", timeout=10_000)
    page.fill("#newProduction", f"E2E offline {uuid.uuid4().hex[:6]}")
    page.click("#createProduction")
    page.wait_for_function("document.querySelector('#production') && document.querySelector('#production').value !== ''", timeout=10_000)
    page.fill("#general_crew_call", "05:45")
    page.fill("#safety_notes", "draft must survive")

    page.route(f"{api_url}/**", lambda route: route.abort())
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("draft is safe", timeout=15_000)

    page.unroute(f"{api_url}/**")
    page.reload()
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    assert page.locator("#general_crew_call").input_value() == "05:45"
    assert page.locator("#safety_notes").input_value() == "draft must survive"
    expect(page.locator("#publishState")).to_contain_text("Not published yet")

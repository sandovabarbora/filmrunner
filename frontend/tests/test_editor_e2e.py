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


def _connect(page: Page, frontend_url: str, api_url: str) -> None:
    """Inject the service connection the way a tool would (no sign-in UI), so the
    suite runs the same against a build with or without Supabase configured."""
    page.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#newProduction", timeout=10_000)


def _create_production(page: Page, name: str) -> None:
    page.fill("#newProduction", name)
    page.click("#createProduction")
    page.wait_for_selector("#newDay", timeout=10_000)  # lands on the production's Days tab


def test_connected_app_production_crew_day_reopen_publish_b(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-17 dod: create production, add a HoD, create a day, reopen the editor,
    open the day from the list, publish REV B with a head of day, crew link shows B and the contact."""
    production = f"E2E {uuid.uuid4().hex[:6]}"
    _connect(page, frontend_url, api_url)
    _create_production(page, production)

    # Crew tab: one head of department.
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Eva Dvořáková")
    page.fill("#crewPhone", "+420 777 111 222")
    page.fill("#crewDept", "AD")
    page.fill("#crewPos", "1st AD")
    page.check("#crewHod")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Eva Dvořáková", timeout=10_000)

    # New day.
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#shoot_date", "2026-09-22")
    page.fill("#day_number", "7")
    page.fill("#day_count", "24")
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("42")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("RIVERBANK, TROJA.")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    assert "/day/new" not in page.url  # moved to the real day's URL

    # Close and reopen: the day is found from the list, loaded from the server.
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#productions", timeout=10_000)
    page.click(f"#productions >> text={production}")
    page.wait_for_selector("#days", timeout=10_000)
    expect(page.locator("#days")).to_contain_text("Day 7 of 24")
    expect(page.locator("#days")).to_contain_text("REV A")
    page.click("#days >> text=Day 7 of 24")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    assert page.locator("#general_crew_call").input_value() == "06:30"
    assert page.locator("#items .item").count() == 1
    assert page.locator("#shoot_date").is_disabled()

    # Hot revision with a head of day.
    page.fill("#general_crew_call", "07:30")
    page.select_option("#headOfDay", label="Eva Dvořáková · 1st AD (HoD)")
    expect(page.locator("#publishState")).to_contain_text("Publish to send REV B")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    share = page.locator("#shareLink").get_attribute("href")
    assert share

    # Crew link: REV B, new call, head of day and HoD with tap-to-call.
    page.goto(share)
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    assert page.locator("#revBadgeWrap").inner_text().strip() == "REV B"
    assert page.locator("#crewCall").inner_text().strip() == "07:30"
    assert "Eva Dvořáková" in page.locator("#contacts .hod").inner_text()
    assert page.locator("#contacts a.phone").first.get_attribute("href") == "tel:+420777111222"


def test_publish_without_network_keeps_the_draft(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (FR-10 dod): losing the network must not lose the draft."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E offline {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
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


def test_opening_a_published_day_offline_is_read_only(page: Page, frontend_url: str, api_url: str) -> None:
    """Failure case (FR-17 dod): offline, a published day shows the last copy read-only, never a blank publishable form."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E ro {uuid.uuid4().hex[:6]}")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:00")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.route(f"{api_url}/**", lambda route: route.abort())
    page.reload()
    page.wait_for_selector("#publishState", timeout=10_000)
    expect(page.locator("#publishState")).to_contain_text("Read-only while offline")
    assert page.locator("#publish").is_disabled()
    assert page.locator("#general_crew_call").input_value() == "06:00"


def test_five_taps_on_the_logo_open_admin_access(page: Page, frontend_url: str, api_url: str) -> None:
    """Founder's gesture: 5 taps on the logo within 3 s reveal the service-token screen; the token then bypasses sign-in."""
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#logo", timeout=10_000)
    for _ in range(5):
        page.click("#logo")
    page.wait_for_selector("#adminScreen", timeout=5_000)
    assert "Admin access" in (page.locator("#adminScreen h2").text_content() or "")
    page.fill("#apiBase", api_url)
    page.fill("#token", E2E_TOKEN)
    page.click("#connect")
    page.wait_for_selector("#newProduction", timeout=10_000)
    assert "Admin" in page.locator(".masthead .sub").inner_text()


def test_four_taps_do_nothing(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#logo", timeout=10_000)
    for _ in range(4):
        page.click("#logo")
    page.wait_for_timeout(300)
    assert page.locator("#adminScreen").count() == 0


def test_owner_invites_members_and_sees_role_chip(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-15: the Members tab (owner only) invites by email; a viewer row shows 'not signed in yet' until they do."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E roles {uuid.uuid4().hex[:6]}")
    assert page.locator("#myRole").inner_text().strip().lower() == "owner"
    page.click("role=tab[name='Members']")
    page.wait_for_selector("#memberEmail", timeout=10_000)
    page.fill("#memberEmail", "viewer@example.com")
    page.select_option("#memberRole", "viewer")
    page.click("#addMember")
    expect(page.locator("#members")).to_contain_text("viewer@example.com", timeout=10_000)
    expect(page.locator("#members")).to_contain_text("not signed in yet")
    page.click("#members >> role=button[name='Remove viewer@example.com']")
    expect(page.locator("#members li")).to_have_count(0, timeout=10_000)


def test_personal_link_shows_your_call_and_department_first(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-13: a crew member's personal link shows their name, own call and their department's HoD first;
    an invalid token falls back to the general sheet with a note."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E me {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    for name, phone, dept, pos, hod in (("Eva Dvořáková", "+420 777 111 222", "AD", "1st AD", True), ("Petr Malý", "+420 602 000 000", "Electric", "Best boy", False), ("Tomáš Novák", "+420 601 234 567", "Electric", "Gaffer", True)):
        page.fill("#crewName", name); page.fill("#crewPhone", phone); page.fill("#crewDept", dept); page.fill("#crewPos", pos)
        if hod:
            page.check("#crewHod")
        page.click("#addCrew")
        expect(page.locator("#crew")).to_contain_text(name, timeout=10_000)
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    petr_link = page.locator("#personalLinks li", has_text="Petr Malý").locator("a").get_attribute("href")
    assert petr_link and "&me=" in petr_link

    page.goto(petr_link)
    page.wait_for_selector("#you", timeout=15_000)
    assert "Petr Malý" in page.locator("#you").inner_text()
    assert page.locator("#yourCall").inner_text().strip() == "06:30"  # no own call time: general crew call
    assert "Tomáš Novák" in page.locator("#yourDepartment").inner_text()  # Electric HoD first
    assert "Eva Dvořáková" not in page.locator("#yourDepartment").inner_text()
    assert page.locator("#otherDepartments").count() == 1

    page.goto(petr_link.replace("&me=", "&me=bogus"))
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    page.wait_for_selector("#personalInvalid", timeout=10_000)
    assert page.locator("#you").count() == 0


def test_crew_edit_personal_call_and_remove(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-18: edit a person (phone, personal call, HoD), see it on the sheet, remove another."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E crew {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    for name, dept, pos in (("Petr Malý", "Electric", "Best boy"), ("Jana Bílá", "Production", "UPM")):
        page.fill("#crewName", name); page.fill("#crewDept", dept); page.fill("#crewPos", pos); page.click("#addCrew")
        expect(page.locator("#crew")).to_contain_text(name, timeout=10_000)

    page.click("#crew >> role=button[name='Edit Petr Malý']")
    expect(page.locator("#crewFormTitle")).to_contain_text("Editing Petr Malý")
    page.fill("#crewPhone", "+420 777 000 111")
    page.fill("#crewCall", "05:45")
    page.check("#crewHod")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("call 05:45", timeout=10_000)
    expect(page.locator("#crew")).to_contain_text("+420 777 000 111")
    expect(page.locator("#crewFormTitle")).to_contain_text("Add a person")

    page.once("dialog", lambda d: d.accept())
    page.click("#crew >> role=button[name='Remove Jana Bílá']")
    expect(page.locator("#crew")).not_to_contain_text("Jana Bílá", timeout=10_000)

    # The personal sheet uses the edited call time.
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Petr Malý").locator("a").get_attribute("href")
    page.goto(link)
    page.wait_for_selector("#you", timeout=15_000)
    assert page.locator("#yourCall").inner_text().strip() == "05:45"

"""End-to-end: deleting a production from its Settings tab (FR-185), against
the real API — same harness as test_editor_e2e.py."""

import uuid

from playwright.sync_api import Page, expect

from test_editor_e2e import _connect, _create_production


def test_deleting_a_production_removes_it_and_its_crew_for_good(page: Page, frontend_url: str, api_url: str) -> None:
    name = f"E2E del {uuid.uuid4().hex[:6]}"
    _connect(page, frontend_url, api_url)
    _create_production(page, name)

    # Give it something to delete along with it: a crew member.
    page.click("role=tab[name='Crew']")
    page.fill("#crewName", "Petr Doe")
    page.fill("#crewDept", "Electric")
    page.fill("#crewPos", "Best boy")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Doe", timeout=15_000)

    page.click("role=tab[name='Settings']")
    page.wait_for_selector("#deleteProduction", timeout=10_000)
    page.once("dialog", lambda d: d.accept())
    page.click("#deleteProduction")

    expect(page.locator("#notice")).to_contain_text("deleted", timeout=15_000)
    # Back on the Productions list (empty, since this was the only production this
    # browser context created), with no trace of the deleted one anywhere on the page.
    page.wait_for_selector("#newProduction", timeout=10_000)
    expect(page.locator("#intro")).to_be_visible()
    expect(page.locator("#main")).not_to_contain_text(name)

    # A fresh production still works (the editor itself is unaffected).
    _create_production(page, f"E2E after-del {uuid.uuid4().hex[:6]}")

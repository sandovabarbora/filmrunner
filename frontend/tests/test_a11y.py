"""FR-63: axe-core over the four screens a crew member and an AD actually use.

A call sheet is read at 05:00 in a car; labels, contrast and focus order are legibility, not polish.
The suite fails on any serious/critical violation; moderate and minor ones are printed (run with -s)
and triaged in docs/research/a11y-2026-09.md.
"""

import json
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from test_editor_e2e import _connect, _create_production

AXE = Path(__file__).resolve().parents[1] / "node_modules" / "axe-core" / "axe.min.js"
BLOCKING = {"serious", "critical"}


def audit(page: Page, label: str) -> list[dict]:
    """Run axe on the current page; returns every violation, prints a summary, asserts none blocking."""
    assert AXE.exists(), "axe-core is a devDependency: run npm ci in frontend/"
    page.add_script_tag(path=str(AXE))
    result = page.evaluate("async () => await axe.run(document, { resultTypes: ['violations'] })")
    violations = result["violations"]
    print(f"\n[a11y] {label}: {len(violations)} violation kinds")
    for v in violations:
        targets = ", ".join(t for node in v["nodes"][:3] for t in node["target"])
        print(f"  {v['impact']:<8} {v['id']:<32} {len(v['nodes'])}× {targets[:90]}")
    blocking = [v for v in violations if v["impact"] in BLOCKING]
    assert not blocking, "serious/critical: " + "; ".join(f"{v['id']} ({v['impact']}) on {v['nodes'][0]['target']}" for v in blocking)
    return violations


@pytest.mark.parametrize("locale", ["en-US", "cs-CZ"])
def test_crew_sheet_demo(browser, frontend_url: str, locale: str) -> None:
    ctx = browser.new_context(locale=locale, viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    audit(page, f"crew sheet, demo, {locale}")
    ctx.close()


def test_personal_link_day_screen_and_crew_tab(page: Page, frontend_url: str, api_url: str) -> None:
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E a11y {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák"); page.fill("#crewPhone", "777 123 456"); page.fill("#crewDept", "Electric"); page.fill("#crewPos", "Gaffer"); page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Tomáš Novák", timeout=10_000)
    audit(page, "editor · Crew tab")

    page.click("role=tab[name='Days']"); page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("42")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("EXT. RIVERBANK")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    audit(page, "editor · day screen, published")
    link = page.locator("#personalLinks li", has_text="Tomáš Novák").get_by_role("link", name="Open").get_attribute("href")

    crew_view = page.context.new_page()
    crew_view.goto(link)
    crew_view.wait_for_selector("#you", timeout=15_000)
    audit(crew_view, "crew sheet via personal link")
    crew_view.close()


@pytest.mark.parametrize("path,label", [("landing.html", "landing"), ("privacy.html", "privacy note")])
def test_public_pages(browser, frontend_url: str, path: str, label: str) -> None:
    """The two pages a prospect and a crew member read before they trust us with a phone number."""
    ctx = browser.new_context(locale="cs-CZ", viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/{path}")
    page.wait_for_selector("h1", timeout=10_000)
    audit(page, label)
    ctx.close()


def test_a_report_of_the_non_blocking_findings_exists(page: Page, frontend_url: str) -> None:
    """The report is part of the deliverable; this keeps it from silently disappearing."""
    report = Path(__file__).resolve().parents[2] / "docs" / "research" / "a11y-2026-09.md"
    assert report.exists(), "docs/research/a11y-2026-09.md is the triage of what axe reports"
    assert "axe-core" in report.read_text(encoding="utf-8")

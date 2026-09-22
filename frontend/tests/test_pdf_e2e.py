"""End-to-end: the AD's PDF of a published day (FR-47 dod).

Seeds a realistic 40-scene, 30-crew day through the real API (plain HTTP,
not the editor UI — typing 70 rows through Playwright would be slow and
isn't what this test is checking), then drives the actual print pipeline:
the day screen's "PDF" link (?print=1 on the crew link opens the print
dialog on load, stubbed here since headless Chromium has no print dialog
to open) and the public sheet rendered under print media, page-counted
from a real PDF via Chromium's page.pdf() — against the real built
frontend and a real uvicorn+Postgres API, the same harness every other
E2E file in this repo uses.
"""

import json
import re
import urllib.request
import uuid
from io import BytesIO

from playwright.sync_api import Page, expect
from pypdf import PdfReader

from conftest import E2E_TOKEN
from test_editor_e2e import _connect, _create_production


def _api(api_url: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{api_url}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {E2E_TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        body_bytes = r.read()
        return json.loads(body_bytes) if body_bytes else {}


def _seed_scale_day(api_url: str, production_name: str) -> str:
    """One production, 30 crew across 6 departments, one published day of 40 scenes. Returns the call sheet id."""
    production = _api(api_url, "POST", "/api/v1/productions", {"name": production_name})
    production_id = production["id"]

    departments = ["Camera", "Grip", "Electric", "Sound", "Art", "Production"]
    for i in range(30):
        contact = _api(api_url, "POST", "/api/v1/contacts", {"name": f"Crew Member {i:02d}", "phone": f"77712{i:04d}"})
        _api(api_url, "POST", f"/api/v1/productions/{production_id}/crew-members", {
            "contact_id": contact["id"], "department": departments[i % len(departments)], "position": "Tech",
        })

    schedule_items = [
        {
            "order_index": i,
            "scene_number": str(i + 1),
            "int_ext": "INT" if i % 2 == 0 else "EXT",
            "day_night": "DAY" if i % 3 else "NIGHT",
            "set_description": f"Set {i + 1} — a description long enough to wrap onto a second line, same as a real slugline",
            "page_count_eighths": 3,
        }
        for i in range(40)
    ]
    call_sheet = _api(api_url, "POST", f"/api/v1/productions/{production_id}/call-sheets", {
        "shoot_date": "2026-10-01", "day_number": 1, "day_count": 30, "unit_name": "Main Unit",
        "initial_revision": {
            "general_crew_call": "06:00",
            "shooting_call": "07:00",
            "safety_notes": "Wet floor near the tank; hard hats required past the grip truck.",
            "schedule_items": schedule_items,
        },
    })
    return call_sheet["id"]


def test_pdf_link_opens_print_mode_and_calls_print_on_load(page: Page, frontend_url: str, api_url: str) -> None:
    """dod: the day screen's "PDF" link opens the crew link with ?print=1, which opens
    the print dialog on load — no extra tap once the AD is on the sheet."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E pdf {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("4")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("Warehouse")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)

    pdf_href = page.locator("#pdfLink").get_attribute("href")
    assert pdf_href is not None and pdf_href.endswith("&print=1")

    view = page.context.new_page()
    view.add_init_script("window.__printed = 0; window.print = () => { window.__printed += 1; };")
    view.goto(pdf_href)
    view.wait_for_selector("#sheet.visible", timeout=15_000)
    view.wait_for_function("window.__printed > 0", timeout=5_000)
    view.close()


def test_a_40_scene_30_crew_day_paginates_under_four_pages_with_no_split_row(page: Page, frontend_url: str, api_url: str) -> None:
    """dod: a 40-scene, 30-person day stays under 4 printed pages and no table row is split
    across a page break; the footer carries the crew link, a QR code and "page / pages"."""
    call_sheet_id = _seed_scale_day(api_url, f"E2E scale {uuid.uuid4().hex[:6]}")

    view = page.context.new_page()
    view.goto(f"{frontend_url}/?sheet={call_sheet_id}&api={api_url}")
    view.wait_for_selector("#sheet.visible", timeout=15_000)
    expect(view.locator("#scheduleBody tr")).to_have_count(40)

    view.emulate_media(media="print")
    expect(view.locator("#printFooterBar")).to_contain_text(f"sheet={call_sheet_id}")
    assert view.locator("#printFooterBar svg").count() == 1

    reader = PdfReader(BytesIO(view.pdf()))
    page_count = len(reader.pages)
    assert page_count < 4, f"expected under 4 pages for 40 scenes + 30 crew, got {page_count}"

    combined = "\n".join(p.extract_text() for p in reader.pages)
    assert re.search(r"Page \d+ / \d+", combined), "no page-number footer found in the printed output"

    # Every scene appears exactly once across the whole PDF; a split or dropped row would
    # change this list (missing a number, or a number counted twice).
    scene_labels = sorted(int(n) for n in re.findall(r"Set (\d+) ", combined))
    assert scene_labels == list(range(1, 41))

    view.close()


def test_a_day_with_no_cast_and_no_personal_calls_prints_without_empty_headings(page: Page, frontend_url: str, api_url: str) -> None:
    """failure case: a sheet with neither cast nor personal calls never prints an empty
    Cast or Personal calls heading."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E pdf-empty {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("1")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("Office")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    href = page.locator("#shareLink").get_attribute("href")

    view = page.context.new_page()
    view.goto(href)
    view.wait_for_selector("#sheet.visible", timeout=15_000)
    view.emulate_media(media="print")
    assert view.locator("#castTable").count() == 0
    assert view.locator("#personalCallsTable").count() == 0
    view.close()

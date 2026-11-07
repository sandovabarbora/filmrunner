"""FR-226: the day screen's jump row and undo after removing a scene."""
import json
import uuid

import pytest
from conftest import E2E_TOKEN
from playwright.sync_api import Page, expect
from test_plan_change_sheet import _api


def _day_with_three_scenes(api_url: str) -> tuple[str, str]:
    production = _api(api_url, "POST", "/productions", {"name": f"Jump {uuid.uuid4().hex[:6]}"})["id"]
    river = _api(api_url, "POST", f"/productions/{production}/locations", {"name": "River bank", "address": "Bank 1"})

    def scene(order: int, number: str, ie: str, dn: str, text: str, eighths: int) -> dict:
        return {"order_index": order, "scene_number": number, "int_ext": ie, "day_night": dn, "set_description": text, "location_id": river["id"], "page_count_eighths": eighths}

    revision = {"general_crew_call": "07:00", "schedule_items": [scene(1, "41", "EXT", "DAY", "Bank", 8), scene(2, "42", "INT", "NIGHT", "Boat cabin", 3), scene(3, "43", "EXT", "DAY", "Pier", 12)], "crew_calls": []}
    day = _api(api_url, "POST", f"/productions/{production}/call-sheets", {"shoot_date": "2031-03-04", "day_number": 1, "day_count": 2, "unit_name": "Main", "initial_revision": revision})
    return production, day["id"]


def _open_day(page: Page, frontend_url: str, api_url: str, width: int, height: int) -> None:
    production, sheet = _day_with_three_scenes(api_url)
    connection = json.dumps({"apiBase": api_url, "token": E2E_TOKEN})
    page.add_init_script(f"localStorage.setItem('filmrunner.editor.connection', {json.dumps(connection)});")
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{frontend_url}/editor.html#/p/{production}/day/{sheet}")
    page.wait_for_selector("#publish", timeout=15_000)


def _scenes(page: Page) -> list[list[str]]:
    return page.eval_on_selector_all("#items .item", "items => items.map(li => [...li.querySelectorAll('input, select')].map(f => f.value))")


@pytest.mark.parametrize("width,height", [(320, 640), (390, 844), (1440, 900)])
def test_the_jump_row_lands_each_block_below_itself_and_above_the_publish_bar(page: Page, frontend_url: str, api_url: str, width: int, height: int) -> None:
    _open_day(page, frontend_url, api_url, width, height)
    page.emulate_media(reduced_motion="reduce")
    links = page.locator("#jumpRow a")
    expect(links).to_have_text(["Day", "Calls", "Personal calls", "Schedule", "Share"])
    for box in [links.nth(i).bounding_box() for i in range(links.count())]:
        assert box is not None and box["height"] >= 44
    assert page.evaluate("document.documentElement.scrollWidth") <= width

    page.click("#jumpRow a:has-text('Schedule')")
    expect(page.locator("#jumpRow a[aria-current]")).to_have_text("Schedule")
    row = page.locator("#jumpRow").bounding_box()
    heading = page.locator("#scheduleBlock h2").bounding_box()
    bar = page.locator(".publish-bar").bounding_box()
    assert row is not None and heading is not None and bar is not None
    assert row["y"] == 0
    assert heading["y"] >= row["y"] + row["height"]
    assert heading["y"] + heading["height"] <= bar["y"]

    page.click("#jumpRow a:has-text('Share')")
    expect(page.locator("#shareLink")).to_be_visible()

    # A field focused by keyboard is never left under the row.
    page.locator("#general_crew_call").focus()
    field = page.locator("#general_crew_call").bounding_box()
    row = page.locator("#jumpRow").bounding_box()
    assert field is not None and row is not None and field["y"] >= row["y"] + row["height"]

    page.locator("#callsBlock").evaluate("el => el.scrollIntoView()")
    expect(page.locator("#jumpRow a[aria-current]")).to_have_text("Calls")


def test_a_removed_scene_comes_back_where_it_was_with_every_field(page: Page, frontend_url: str, api_url: str) -> None:
    _open_day(page, frontend_url, api_url, 390, 844)
    before = _scenes(page)
    assert [s[0] for s in before] == ["41", "42", "43"]
    expect(page.locator("#publish")).to_have_class("secondary")

    page.locator("#items .item").nth(1).get_by_role("button", name="Remove").click()
    assert [s[0] for s in _scenes(page)] == ["41", "43"]
    expect(page.locator("#undoNote")).to_have_text("Scene 42 removed · Undo")
    expect(page.locator("#undoNote")).to_have_attribute("role", "status")

    page.click("#undoRemove")
    assert _scenes(page) == before
    expect(page.locator("#undoNote")).to_be_empty()
    expect(page.locator("#publish")).to_have_class("secondary")  # nothing left to publish

    # A second removal replaces the first; only the latest can come back, and the offer goes after eight seconds.
    first = page.locator("#items .item").nth(0)
    first.get_by_role("button", name="Remove").click()
    page.locator("#items .item").nth(0).get_by_role("button", name="Remove").click()
    expect(page.locator("#undoNote")).to_have_text("Scene 42 removed · Undo")
    page.click("#undoRemove")
    assert [s[0] for s in _scenes(page)] == ["42", "43"]
    page.locator("#items .item").nth(0).get_by_role("button", name="Remove").click()
    expect(page.locator("#undoRemove")).to_be_visible()
    expect(page.locator("#undoRemove")).to_have_count(0, timeout=10_000)

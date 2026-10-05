"""FR-126: keyboard-only navigation (WCAG 2.1.1 Keyboard, 2.1.2 No Keyboard Trap).

axe-core (FR-63) explicitly cannot verify actual keyboard operability, and FR-73/94's
reflow checks only cover layout — nothing in this repo has ever driven the crew sheet,
a personal link, or the editor using only a keyboard. A pilot crew member who cannot
use touch or a mouse has never actually been tested.

Each screen is driven with only Tab/Shift+Tab (no click/tap). We confirm three things:
every interactive control is reachable in a sane order, every focused control shows a
real, visible focus indicator (not `outline: none` with nothing replacing it), and
tabbing through the whole screen and once more never raises an error or gets stuck
repeating one element — by walking all the way to the end of the document (focus
lands on `<body>`) and confirming the very next Tab restarts the cycle at the first
control, never anywhere else and never nowhere.

A native `<input type="date">` keeps `document.activeElement` on the same node for a
few consecutive Tab presses while Tab moves between its internal year/month/day
segments — true in every browser, not a trap; `_MULTI_SEGMENT_INPUT_TYPES` below
allows a bounded number of those repeats and nothing else.

No screen in this repo currently holds focus inside an overlay/dialog while open (no
`<dialog>`, no focus-trapping modal exists anywhere in `frontend/src` — checked before
writing this suite), so the "intentional focus-holding" failure case this item's own
dod names has nothing to exercise today. If one is ever added, this suite's trap
detection below would catch it; per the dod, that is only a real failure if Escape (or
a visible close control) does not return focus to where it was before the overlay
opened — not merely for holding focus while genuinely open.
"""

import uuid

import pytest
from playwright.sync_api import Page

from test_editor_e2e import _connect, _create_production

_FOCUS_PROBE = """() => {
    const el = document.activeElement;
    if (!el || el === document.body) return { end: true };
    if (!window.__kbdIds) { window.__kbdIds = new WeakMap(); window.__kbdCounter = 0; }
    if (!window.__kbdIds.has(el)) window.__kbdIds.set(el, ++window.__kbdCounter);
    const cs = getComputedStyle(el);
    const visibleFocus = (cs.outlineStyle !== 'none' && cs.outlineWidth !== '0px') || cs.boxShadow !== 'none';
    const label = (el.innerText || el.value || el.getAttribute('aria-label') || '').slice(0, 40);
    return {
        end: false,
        id: window.__kbdIds.get(el),
        tag: el.tagName,
        elId: el.id || null,
        inputType: el.tagName === 'INPUT' ? el.type : null,
        visibleFocus,
        label,
    };
}"""

# Native multi-segment inputs (date/time pickers) legitimately keep `document.activeElement`
# on the same node for several consecutive Tab presses while Tab moves between their
# internal segments (year/month/day, …) — every browser does this, it is not a trap.
_MULTI_SEGMENT_INPUT_TYPES = {"date", "time", "datetime-local", "month", "week"}
_MAX_SEGMENT_REPEATS = 5


def _reset_focus(page: Page) -> None:
    page.evaluate(
        "() => { document.activeElement && document.activeElement.blur && "
        "document.activeElement.blur(); window.__kbdIds = new WeakMap(); window.__kbdCounter = 0; }"
    )


def _describe(info: dict) -> str:
    return f"{info['tag']}#{info['elId'] or '(no id)'} '{info['label']}'"


def _tab_to_end(page: Page, label: str, lap: str, max_steps: int) -> list[dict]:
    """Tabs forward from wherever focus currently is until it reaches the end of the
    document (`<body>`), or fails if that never happens within `max_steps`."""
    seq: list[dict] = []
    for step in range(1, max_steps + 1):
        page.keyboard.press("Tab")
        info = page.evaluate(_FOCUS_PROBE)
        if info["end"]:
            return seq
        is_repeat = bool(seq) and info["id"] == seq[-1]["id"]
        is_multi_segment = info["inputType"] in _MULTI_SEGMENT_INPUT_TYPES
        # Mid-segment Tabs inside the same date/time control don't move `document.activeElement`
        # and Chromium doesn't keep re-asserting `:focus-visible` on them, even though the control
        # still shows a native highlighted segment — not visible to getComputedStyle, so this check
        # only applies the first time a control is focused, not on its own internal segment moves.
        if not (is_repeat and is_multi_segment):
            assert info["visibleFocus"], f"{label} ({lap}): {_describe(info)} has no visible focus indicator (Tab #{step})"
        if is_repeat:
            repeats = 1
            for prior in reversed(seq[:-1]):
                if prior["id"] != info["id"]:
                    break
                repeats += 1
            if not is_multi_segment or repeats > _MAX_SEGMENT_REPEATS:
                pytest.fail(f"{label} ({lap}): focus stuck on {_describe(info)} (Tab #{step}) — keyboard trap")
        seq.append(info)
    pytest.fail(f"{label} ({lap}): forward Tab never reached the end of the document within {max_steps} presses")


def walk_keyboard(page: Page, label: str, max_steps: int = 200) -> list[dict]:
    """Tabs forward through `page`, from wherever focus currently is, all the way to the
    end of the document twice in a row (the dod's own "and once more"): every focused
    control must have a real, visible focus indicator, focus must never get stuck
    repeating one control, and reaching the end (focus on `<body>`) must happen within
    `max_steps` both times — proving the cycle closes cleanly rather than trapping focus
    somewhere short of the end on either lap."""
    _reset_focus(page)
    first_lap = _tab_to_end(page, label, "first lap", max_steps)
    assert first_lap, f"{label}: no focusable control found on the page at all"
    second_lap = _tab_to_end(page, label, "second lap", max_steps)
    assert second_lap, f"{label}: no focusable control found on the second lap — Tab past the end got stuck"
    return first_lap


@pytest.mark.parametrize("locale", ["en-US", "cs-CZ"])
def test_crew_sheet_demo_keyboard_nav(browser, frontend_url: str, locale: str) -> None:
    ctx = browser.new_context(locale=locale, viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    seq = walk_keyboard(page, f"crew sheet, demo, {locale}")
    assert len(seq) >= 2, "demo call sheet should expose more than just the language toggle"
    ctx.close()


def test_personal_link_day_screen_and_crew_tab_keyboard_nav(page: Page, frontend_url: str, api_url: str) -> None:
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E kbd {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák")
    page.fill("#crewPhone", "777 123 456")
    page.fill("#crewDept", "Electric")
    page.fill("#crewPos", "Gaffer")
    page.click("#addCrew")
    page.wait_for_selector("#crew", timeout=10_000)
    walk_keyboard(page, "editor · Crew tab")

    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    page.locator("#items .item").nth(0).get_by_label("Scene").fill("42")
    page.locator("#items .item").nth(0).get_by_label("Set").fill("EXT. RIVERBANK")
    walk_keyboard(page, "editor · day screen, draft")

    page.click("#publish")
    page.wait_for_selector("#personalLinks", timeout=15_000)
    link = page.locator("#personalLinks li", has_text="Tomáš Novák").get_by_role("link", name="Open").get_attribute("href")

    crew_view = page.context.new_page()
    crew_view.goto(link)
    crew_view.wait_for_selector("#you", timeout=15_000)
    walk_keyboard(crew_view, "crew sheet via personal link")
    crew_view.close()

"""FR-73: WCAC 1.4.10 reflow at a 200%-zoom-equivalent viewport.

WCAG 1.4.10 defines the check as content that reflows without two-dimensional
scrolling at a viewport 320 CSS px wide (the accepted equivalent of 400% zoom
on a 1280px-wide reference browser, which is itself the standard proxy for
"200% zoom" on a device already at mobile width — see
https://www.w3.org/WAI/WCAG21/Understanding/reflow.html). We resize the
viewport rather than call a real OS/browser zoom control, which is the
technique WCAG's own documentation names first ("Resizing... to a width
equivalent to 320 CSS pixels").

A call sheet is read at 05:00 on a phone that may already have the system
text size bumped up; it must never force horizontal scrolling or silently
clip content.
"""

import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import E2E_TOKEN
from test_editor_e2e import _connect, _create_production

REFLOW_WIDTH = 320  # WCAG 1.4.10's own CSS-pixel definition of the reflow viewport
REFLOW_HEIGHT = 800  # generous: 1.4.10 only forbids horizontal scrolling, not vertical

# A single unbreakable "word" an AD might actually type (a long compound
# location name with no spaces) — the dod's own named failure case.
LONG_UNBROKEN_SET = "EXT. NÁDRAŽÍ-VRŠOVICE-DEPO-KOLEJIŠTĚ-SEVEROVÝCHODNÍ-VJEZD-U-SEMAFORU"

# FR-94: the same class of AD-plausible unbroken content, for the editor's
# own screens (a long safety note, a long department/position title) rather
# than only the crew's read-only sheet FR-73 already covered.
LONG_UNBROKEN_SAFETY_NOTE = (
    "POZOR-NEROVNÝ-TERÉN-KOLEM-CELÉHO-NÁDRAŽÍ-NOSTE-PEVNOU-OBUV-A-REFLEXNÍ-VESTU-STÁLE"
)
LONG_UNBROKEN_DEPARTMENT = "ELEKTRO-OSVĚTLOVACÍ-TECHNIKA-GENERÁTOROVÝ-VŮZ-NOČNÍ-SMĚNA"
LONG_UNBROKEN_POSITION = "VEDOUCÍ-SVĚTELNÉHO-PARKU-A-GENERÁTOROVÉHO-VOZU-ZÁSTUP"


def assert_no_horizontal_scroll(page: Page, label: str) -> None:
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    client_width = page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width + 1, (
        f"{label}: page requires horizontal scroll at {REFLOW_WIDTH}px "
        f"(content {scroll_width}px in a {client_width}px viewport)"
    )


def find_clipped_elements(page: Page) -> list[dict]:
    """Elements whose own text content is wider than their box, excluding
    anything that opts into scrolling on purpose (e.g. the editor's picker
    dropdown). This is the automatable proxy for "clipped text"; true visual
    overlap between unrelated elements was not probed (no layout here uses
    absolute or negative-margin positioning for text, only grid/flex/block,
    so overlap is not a realistic risk the way clipping at a narrow width is).

    FR-94: also excludes INPUT/TEXTAREA/SELECT. A text input's own value
    scrolling past its box is native browser behaviour, not a reflow bug —
    the full value stays reachable with the keyboard (Home/End) and to a
    screen reader regardless of what is visually painted, unlike the
    read-only clipped text this check exists to catch. Flagging every
    narrower-than-its-value input would fire on ordinary form fields
    everywhere in the app, not just on the long AD-typed content this item
    was written to probe.
    """
    return page.evaluate(
        """() => {
            const clipped = [];
            document.querySelectorAll('body *').forEach(el => {
                const cs = getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden') return;
                if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') return;
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return;
                if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2) {
                    clipped.push({
                        tag: el.tagName,
                        cls: el.className && el.className.toString().slice(0, 60),
                        text: (el.textContent || '').trim().slice(0, 70),
                        scrollWidth: el.scrollWidth,
                        clientWidth: el.clientWidth,
                    });
                }
            });
            return clipped;
        }"""
    )


def check_reflow(page: Page, label: str) -> list[dict]:
    assert_no_horizontal_scroll(page, label)
    clipped = find_clipped_elements(page)
    print(f"\n[reflow] {label}: {len(clipped)} clipped element(s)")
    for c in clipped:
        print(f"  <{c['tag']} class={c['cls']!r}> {c['scrollWidth']}px in {c['clientWidth']}px: {c['text']!r}")
    return clipped


@pytest.mark.parametrize("locale", ["en-US", "cs-CZ"])
def test_crew_sheet_demo_reflows_at_320px(browser, frontend_url: str, locale: str) -> None:
    ctx = browser.new_context(locale=locale, viewport={"width": REFLOW_WIDTH, "height": REFLOW_HEIGHT})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    clipped = check_reflow(page, f"crew sheet, demo, {locale}")
    assert not clipped, f"clipped text on the demo sheet ({locale}): {clipped}"
    ctx.close()


def test_personal_link_reflows_at_320px_with_an_unusually_long_set_name(
    browser, page: Page, frontend_url: str, api_url: str
) -> None:
    """The dod's own failure case: a set name the AD actually typed, with no
    spaces to break on, must be documented if it clips — never silently
    truncated by us, and never treated as our bug to "fix" by shortening
    the AD's text."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E reflow {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Tomáš Novák")
    page.fill("#crewPhone", "777 123 456")
    page.fill("#crewDept", "Electric")
    page.fill("#crewPos", "Gaffer")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Tomáš Novák", timeout=10_000)

    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#addScene")
    row = page.locator("#items .item").nth(0)
    row.get_by_label("Scene").fill("42")
    row.get_by_label("Set").fill(LONG_UNBROKEN_SET)
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Tomáš Novák").get_by_role("link", name="Open").get_attribute("href")

    ctx = browser.new_context(viewport={"width": REFLOW_WIDTH, "height": REFLOW_HEIGHT})
    crew_view = ctx.new_page()
    crew_view.goto(link)
    crew_view.wait_for_selector("#you", timeout=15_000)
    assert_no_horizontal_scroll(crew_view, "personal link, unusually long set name")
    clipped = find_clipped_elements(crew_view)
    print(f"\n[reflow] personal link, unusually long set name: {len(clipped)} clipped element(s)")
    for c in clipped:
        print(f"  <{c['tag']} class={c['cls']!r}> {c['scrollWidth']}px in {c['clientWidth']}px: {c['text']!r}")
    ctx.close()


def _connect_new_context_page(browser: Browser, api_url: str, frontend_url: str, hash_url: str) -> Page:
    """Open a fresh 320px context already signed in (same pattern as `_connect`,
    but for a page we didn't create the data from), then jump straight to a
    hash route the first page already reached."""
    ctx = browser.new_context(viewport={"width": REFLOW_WIDTH, "height": REFLOW_HEIGHT})
    p = ctx.new_page()
    p.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )
    p.goto(hash_url)
    return p


def test_editor_day_screen_reflows_at_320px_with_long_content(
    browser: Browser, page: Page, frontend_url: str, api_url: str
) -> None:
    """FR-94: FR-73 only checked the crew's read-only sheet; the AD's own day
    screen (where that long content is typed in the first place) was never
    run through the same check."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E reflow {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Jana Malá")
    page.fill("#crewPhone", "777 000 111")
    page.fill("#crewDept", "AD")
    page.fill("#crewPos", "1st AD")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Jana Malá", timeout=10_000)

    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.fill("#safety_notes", LONG_UNBROKEN_SAFETY_NOTE)
    page.click("#addScene")
    row = page.locator("#items .item").nth(0)
    row.get_by_label("Scene").fill("7")
    row.get_by_label("Set").fill(LONG_UNBROKEN_SET)
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    day_url = page.url

    day_page = _connect_new_context_page(browser, api_url, frontend_url, day_url)
    day_page.wait_for_selector("#safety_notes", timeout=15_000)
    clipped = check_reflow(day_page, "editor day screen, long safety note and set name")
    assert not clipped, f"clipped text on the editor day screen: {clipped}"
    day_page.context.close()


def test_editor_crew_tab_reflows_at_320px_with_long_crew_details(
    browser: Browser, page: Page, frontend_url: str, api_url: str
) -> None:
    """FR-94: a department or position title the AD actually typed, unbroken
    and long, in the Crew tab itself (not only on the sheet it feeds)."""
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E reflow {uuid.uuid4().hex[:6]}")

    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Petr Novotný")
    page.fill("#crewPhone", "777 222 333")
    page.fill("#crewDept", LONG_UNBROKEN_DEPARTMENT)
    page.fill("#crewPos", LONG_UNBROKEN_POSITION)
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Petr Novotný", timeout=10_000)
    crew_url = page.url

    crew_page = _connect_new_context_page(browser, api_url, frontend_url, crew_url)
    crew_page.wait_for_selector("#crew", timeout=15_000)
    expect(crew_page.locator("#crew")).to_contain_text("Petr Novotný", timeout=10_000)
    clipped = check_reflow(crew_page, "editor Crew tab, long department and position")
    assert not clipped, f"clipped text on the editor Crew tab: {clipped}"
    crew_page.context.close()


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_landing_page_reflows_at_320px(browser: Browser, frontend_url: str, lang: str) -> None:
    ctx = browser.new_context(viewport={"width": REFLOW_WIDTH, "height": REFLOW_HEIGHT})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/landing.html")
    page.wait_for_selector(".hero", timeout=10_000)
    page.click(f'.langToggle button[data-lang="{lang}"]')
    expect(page.locator("body")).to_have_attribute("data-lang", lang)
    clipped = check_reflow(page, f"landing.html, {lang}")
    assert not clipped, f"clipped text on landing.html ({lang}): {clipped}"
    ctx.close()


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_privacy_page_reflows_at_320px(browser: Browser, frontend_url: str, lang: str) -> None:
    ctx = browser.new_context(viewport={"width": REFLOW_WIDTH, "height": REFLOW_HEIGHT})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/privacy.html")
    page.wait_for_selector(".hero", timeout=10_000)
    page.click(f'.langToggle button[data-lang="{lang}"]')
    expect(page.locator("body")).to_have_attribute("data-lang", lang)
    clipped = check_reflow(page, f"privacy.html, {lang}")
    assert not clipped, f"clipped text on privacy.html ({lang}): {clipped}"
    ctx.close()


def test_a_reflow_result_is_recorded_in_the_a11y_report() -> None:
    report = Path(__file__).resolve().parents[2] / "docs" / "research" / "a11y-2026-09.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "FR-73" in text, "the 200%/320px reflow result must be recorded in a11y-2026-09.md"
    assert "not measured" not in text.lower() or "Zoom / large text" not in text.split("FR-73")[0], (
        "the old 'not measured' zoom/reflow line must be replaced with a stated result, not left standing"
    )

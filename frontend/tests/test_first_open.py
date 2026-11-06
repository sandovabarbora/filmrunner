"""FR-221: what a crew member sees on first opening their link, with a real service worker.

Playwright's page.route does not see requests a service worker re-issues, and those are the ones
that matter here, so faults come from a small API on its own port. That port is also a different
origin from the page, as the Fly API is from GitHub Pages. "No signal" closes that port, because
context.set_offline does not reach a worker's own fetches, and to the worker a refused connection
is the same failed fetch.
"""

import http.server
import json
import re
import socketserver
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, BrowserType, Error as PlaywrightError, Page, expect

from test_editor_e2e import _connect, _create_production

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"
MIN_TAP = 44
TODAY_ID = "day-today"
TOMORROW_ID = "day-tomorrow"
HOLD_LIMIT_S = 40

IPHONE = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 3,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
}


def _sheet(sheet_id: str, letter: str) -> dict:
    return {
        "id": sheet_id,
        "production_title": "Zkouska",
        "status": "published",
        "shoot_date": "2026-11-10",
        "day_number": 3,
        "day_count": 9,
        "unit_name": "Main Unit",
        "current_revision": {"revision_letter": letter, "general_crew_call": "06:30", "schedule_items": []},
        "contacts": {
            "department_heads": [
                {"department": "Electric", "name": "Tomas Novak", "phone": None},
                {"department": "Camera", "name": "Eva Mala", "phone": None},
            ],
        },
    }


def _personal(letter: str) -> dict:
    return {
        "name": "Petr Svoboda", "department": "Electric", "position": "Best boy", "personal_call": "05:45",
        "revision_letter": letter, "confirmed_at": None, "is_cast": False, "works_today": True, "department_head": None,
    }


NEXT_DAY = {
    "production_name": "Zkouska",
    "crew_member_name": "Petr Svoboda",
    "call_sheet_id": TODAY_ID,
    "days": [
        {"call_sheet_id": TODAY_ID, "shoot_date": "2026-11-10", "day_number": 3, "day_count": 9, "unit_name": "Main Unit", "revision_letter": "B", "status": "published"},
        {"call_sheet_id": TOMORROW_ID, "shoot_date": "2026-11-11", "day_number": 4, "day_count": 9, "unit_name": "Main Unit", "revision_letter": "A", "status": "published", "general_crew_call": "07:00"},
    ],
}


class CrewApi:
    """Answers the public routes the viewer calls; each route can be told to fail or wait."""

    def __init__(self) -> None:
        self.letter = "B"
        self.status: dict[str, int] = {}
        self.delay: dict[str, float] = {}
        self.gate = threading.Event()
        self.gate.set()
        self.hits: Counter[str] = Counter()
        self.lose_signal: Callable[[], None] = lambda: None

    @staticmethod
    def route_of(path: str) -> str:
        if "/me/" in path:
            return "me"
        if "/seen/" in path:
            return "seen"
        if "/confirm/" in path:
            return "confirm"
        if "/public/crew/" in path:
            return "next"
        if "/call-sheets/" in path:
            return "sheet"
        return "other"

    def set_fault(self, route: str, *, status: int | None = None, delay: float | None = None) -> None:
        if status is None:
            self.status.pop(route, None)
        else:
            self.status[route] = status
        if delay is None:
            self.delay.pop(route, None)
        else:
            self.delay[route] = delay

    def clear(self) -> None:
        self.status.clear()
        self.delay.clear()
        self.gate.set()

    def body_for(self, route: str, path: str) -> dict:
        if route == "me":
            return _personal(self.letter)
        if route == "next":
            return NEXT_DAY
        if route == "confirm":
            return {"confirmed_at": "2026-11-09T18:00:00Z"}
        if route == "sheet":
            return _sheet(path.rstrip("/").rsplit("/", 1)[-1], self.letter)
        return {}


@pytest.fixture
def crew_api() -> Iterator[tuple[CrewApi, str]]:
    state = CrewApi()
    closed = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # noqa: D102
            pass

        def _send(self, status: int, payload: bytes) -> None:
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "*")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_OPTIONS(self) -> None:
            self._send(200, b"")

        def _answer(self) -> None:
            route = CrewApi.route_of(self.path)
            state.hits[route] += 1
            if route == "sheet":
                state.gate.wait(HOLD_LIMIT_S)
            delay = state.delay.get(route)
            if delay:
                time.sleep(delay)
            status = state.status.get(route)
            try:
                if status is not None:
                    self._send(status, b'{"detail":"fault"}')
                elif route == "other":
                    self._send(404, b'{"detail":"not found"}')
                else:
                    self._send(200, json.dumps(state.body_for(route, self.path)).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass  # the viewer gave up first, which is the case under test

        def do_GET(self) -> None:
            self._answer()

        def do_POST(self) -> None:
            self._answer()

    class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def lose_signal() -> None:
        if not closed.is_set():
            closed.set()
            server.shutdown()
            server.server_close()

    state.lose_signal = lose_signal
    yield state, f"http://127.0.0.1:{server.server_address[1]}"
    state.gate.set()
    lose_signal()


@pytest.fixture
def phone(browser: Browser) -> Iterator[BrowserContext]:
    ctx = browser.new_context(locale="cs-CZ", **IPHONE)
    yield ctx
    ctx.close()


def _crew_link(frontend_url: str, api: str, sheet: str = TODAY_ID) -> str:
    return f"{frontend_url}/index.html?api={api}&sheet={sheet}&me=tok123"


def _controlled(page: Page) -> None:
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=20_000)


def _wait_for_worker_cache(page: Page, needle: str) -> None:
    page.wait_for_function(
        "(needle) => caches.open('filmrunner-api-v1').then((c) => c.keys()).then((k) => k.some((r) => r.url.includes(needle)))",
        arg=needle, timeout=10_000,
    )


def _saved_visit(page: Page, link: str) -> None:
    """A first visit that ends with the sheet saved in both of the phone's layers."""
    page.goto(link)
    page.wait_for_selector("#you", timeout=15_000)
    _controlled(page)
    # The first answer can have bypassed the worker; the re-check on controllerchange fills its cache.
    page.wait_for_function("document.querySelector('#status').classList.contains('online')", timeout=10_000)
    page.goto(link)
    page.wait_for_selector("#you", timeout=15_000)
    _wait_for_worker_cache(page, "/me/")
    _wait_for_worker_cache(page, TODAY_ID)


def test_worker_taking_control_mid_load_still_reads_live_and_confirm_works(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    """The audit's 7 of 8: the answer arrives after clients.claim(), unstamped because it never went through the worker."""
    api, url = crew_api
    api.gate.clear()
    page = phone.new_page()
    page.goto(_crew_link(frontend_url, url))
    _controlled(page)
    api.gate.set()
    page.wait_for_selector("#you", timeout=15_000)

    status = page.locator("#status")
    expect(status).to_have_class(re.compile(r"\bonline\b"))
    expect(status).to_contain_text("Živě")
    expect(status).not_to_contain_text("Neznámá")
    expect(page.locator("#confirmBtn")).to_be_enabled()
    page.click("#confirmBtn")
    page.wait_for_selector("#confirmDone", timeout=10_000)


def test_controllerchange_rechecks_exactly_once(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    page = phone.new_page()
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector("#you", timeout=15_000)
    _controlled(page)
    # The re-check sends this through the worker for the first time, so a later offline open has its copy.
    _wait_for_worker_cache(page, TODAY_ID)
    page.wait_for_timeout(1_500)
    assert api.hits["sheet"] == 2
    expect(page.locator("#status")).to_have_class(re.compile(r"\bonline\b"))


def test_several_fresh_phones_all_read_live(crew_api, browser: Browser, frontend_url: str) -> None:
    api, url = crew_api
    for _ in range(4):
        ctx = browser.new_context(locale="cs-CZ", **IPHONE)
        page = ctx.new_page()
        page.goto(_crew_link(frontend_url, url))
        page.wait_for_selector("#you", timeout=15_000)
        _controlled(page)
        page.wait_for_timeout(300)
        expect(page.locator("#status")).to_have_class(re.compile(r"\bonline\b"))
        expect(page.locator("#confirmBtn")).to_be_enabled()
        ctx.close()


def test_a_returning_phone_sees_the_stamp_across_origins(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    """The stamp is read from a response to a cross-origin request; if the page could not read it, every repeat open would be unknown."""
    api, url = crew_api
    page = phone.new_page()
    link = _crew_link(frontend_url, url)
    _saved_visit(page, link)
    expect(page.locator("#status")).to_have_class(re.compile(r"\bonline\b"))


def test_unstamped_answer_from_a_controlling_worker_stays_unknown_but_can_confirm(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    sw_path = DIST_DIR / "sw.js"
    original = sw_path.read_text()
    sw_path.write_text(
        "self.addEventListener('install', () => self.skipWaiting());"
        "self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));"
        "self.addEventListener('fetch', (e) => {"
        "  if (e.request.url.includes('/api/v1/public/call-sheets/')) e.respondWith(fetch(e.request));"
        "});"
    )
    try:
        page = phone.new_page()
        page.goto(f"{frontend_url}/index.html?dev=1")
        _controlled(page)
        page.goto(_crew_link(frontend_url, url))
        page.wait_for_selector("#you", timeout=15_000)
        status = page.locator("#status")
        expect(status).to_have_class(re.compile(r"\boffline\b"))
        expect(status).not_to_contain_text("Živě")
        for wrong in ("zavři", "Reinstall", "znovu", "Neznámá"):
            expect(status).not_to_contain_text(wrong)
        expect(status).to_contain_text("AD")
        expect(page.locator("#confirmBtn")).to_be_enabled()
    finally:
        sw_path.write_text(original)


@pytest.mark.parametrize("cut", ["server_down", "no_signal"])
def test_cached_banner_names_the_revision_and_is_true_both_ways(crew_api, phone: BrowserContext, frontend_url: str, cut: str) -> None:
    api, url = crew_api
    page = phone.new_page()
    link = _crew_link(frontend_url, url)
    _saved_visit(page, link)
    seen_before = api.hits["seen"]

    if cut == "server_down":
        for route in ("sheet", "me", "next"):
            api.set_fault(route, status=503)
    else:
        api.lose_signal()
    page.goto(link)
    page.wait_for_selector("#sheet.visible", timeout=15_000)

    status = page.locator("#status")
    expect(status).to_have_class(re.compile(r"\boffline\b"))
    text = status.inner_text()
    assert "REV B" in text, text
    assert "AD" in text, text
    assert not re.search(r"offline|živě", text, re.IGNORECASE), text
    assert re.search(r"\d{1,2}:\d{2}", text), f"no saved time in: {text}"
    assert "offline" not in page.locator("#cachedAt").inner_text().lower()
    assert "signál" not in page.locator("#confirmOffline").inner_text().lower()
    expect(page.locator("#confirmBtn")).to_be_disabled()
    assert api.hits["seen"] == seen_before  # a saved copy is no read receipt


def test_showing_the_saved_copy_does_not_make_it_newer(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    page = phone.new_page()
    link = _crew_link(frontend_url, url)
    _saved_visit(page, link)
    read_saved = """() => new Promise((resolve, reject) => {
      const open = indexedDB.open('filmrunner-callsheets', 1);
      open.onerror = () => reject(open.error);
      open.onsuccess = () => {
        const get = open.result.transaction('callsheets').objectStore('callsheets').get(%r);
        get.onsuccess = () => resolve(get.result.fetchedAt);
      };
    })""" % TODAY_ID
    before = page.evaluate(read_saved)
    page.wait_for_timeout(50)
    api.lose_signal()
    page.goto(link)
    page.wait_for_selector("#cachedAt", timeout=15_000)
    assert page.evaluate(read_saved) == before


@pytest.mark.parametrize("fault", [500, 429, "timeout"])
def test_a_personal_block_fault_is_not_called_an_invalid_link(crew_api, phone: BrowserContext, frontend_url: str, fault: int | str) -> None:
    api, url = crew_api
    if fault == "timeout":
        api.set_fault("me", delay=HOLD_LIMIT_S)
    else:
        api.set_fault("me", status=fault)
    page = phone.new_page()
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector("#personalUnreachable", timeout=20_000)
    assert page.locator("#personalInvalid").count() == 0
    assert "seznamu" not in page.locator("main").inner_text()
    assert page.locator("#you").count() == 0
    expect(page.locator("#sheet.visible")).to_be_visible()

    api.set_fault("me")
    page.click("#personalRetry")
    page.wait_for_selector("#you", timeout=10_000)
    assert page.locator("#personalUnreachable").count() == 0


@pytest.mark.parametrize("fault", [500, 429, "timeout"])
def test_a_personal_block_fault_with_a_saved_copy_says_so(crew_api, phone: BrowserContext, frontend_url: str, fault: int | str) -> None:
    api, url = crew_api
    page = phone.new_page()
    link = _crew_link(frontend_url, url)
    _saved_visit(page, link)
    if fault == "timeout":
        api.set_fault("me", delay=HOLD_LIMIT_S)
    else:
        api.set_fault("me", status=fault)
    page.goto(link)
    page.wait_for_selector("#personalSaved", timeout=15_000)
    assert page.locator("#personalInvalid").count() == 0
    assert page.locator("#personalUnreachable").count() == 0
    assert page.locator("#yourCall").inner_text() == "05:45"
    assert re.search(r"\d{1,2}:\d{2}", page.locator("#personalSaved").inner_text())


def test_only_a_real_404_calls_the_link_invalid(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    api.set_fault("me", status=404)
    page = phone.new_page()
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector("#personalInvalid", timeout=15_000)
    assert page.locator("#personalUnreachable").count() == 0


def test_cold_server_seven_seconds_on_a_first_open_still_loads_live(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    api.set_fault("sheet", delay=7)
    api.set_fault("me", delay=7)
    api.set_fault("next", delay=7)
    page = phone.new_page()
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector(".skeleton", timeout=5_000)
    page.wait_for_selector("#slowLoad", timeout=6_000)
    assert page.locator("#sheet.visible").count() == 0
    assert page.locator("#status").inner_text().strip() == ""
    page.wait_for_selector("#you", timeout=12_000)
    assert page.locator(".skeleton").count() == 0
    assert page.locator("#slowLoad").count() == 0
    expect(page.locator("#status")).to_have_class(re.compile(r"\bonline\b"))


def test_cold_server_through_a_controlling_worker_with_nothing_in_its_cache(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    """The worker's own 5 s timeout must not cut a first load short once it controls the page."""
    api, url = crew_api
    page = phone.new_page()
    page.goto(f"{frontend_url}/index.html?dev=1")
    _controlled(page)
    api.set_fault("sheet", delay=7)
    api.set_fault("me", delay=7)
    page.goto(_crew_link(frontend_url, url, "never-opened"))
    page.wait_for_selector("#you", timeout=15_000)
    expect(page.locator("#status")).to_have_class(re.compile(r"\bonline\b"))
    assert page.locator("#personalUnreachable").count() == 0


def test_with_a_saved_copy_a_slow_server_falls_back_after_five_seconds(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    page = phone.new_page()
    link = _crew_link(frontend_url, url)
    _saved_visit(page, link)
    api.set_fault("sheet", delay=HOLD_LIMIT_S)
    started = time.monotonic()
    page.goto(link)
    page.wait_for_selector("#cachedAt", timeout=12_000)
    assert time.monotonic() - started < 8
    expect(page.locator("#status")).to_contain_text("REV B")


def test_a_server_that_never_answers_ends_in_a_message_not_a_blank_screen(crew_api, phone: BrowserContext, frontend_url: str) -> None:
    api, url = crew_api
    api.set_fault("sheet", delay=HOLD_LIMIT_S)
    page = phone.new_page()
    started = time.monotonic()
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector(".skeleton", timeout=5_000)
    expect(page.locator("#status")).to_have_class(re.compile(r"\berror\b"), timeout=20_000)
    assert time.monotonic() - started > 12
    assert page.locator(".skeleton").count() == 0
    assert page.locator(".empty").inner_text().strip()


def _assert_tap_target(page: Page, selector: str) -> None:
    box = page.locator(selector).first.bounding_box()
    assert box, f"{selector} has no box"
    assert box["height"] >= MIN_TAP, f"{selector} is {box['height']:.1f}px tall"
    assert box["width"] >= MIN_TAP, f"{selector} is {box['width']:.1f}px wide"
    # Height alone can lie: a neighbour on top of the box would still take the tap.
    hit = page.locator(selector).first.evaluate(
        """(el) => {
          el.scrollIntoView({ block: 'center' });
          const s = el.getBoundingClientRect();
          return [s.top + 1, s.bottom - 1].every((y) => {
            const found = document.elementFromPoint(s.left + Math.min(s.width / 2, 20), y);
            return found === el || el.contains(found);
          });
        }"""
    )
    assert hit, f"{selector}: its top or bottom edge belongs to something else"


@pytest.mark.parametrize("width", [390, 320])
def test_crew_sheet_links_and_summary_are_44px(crew_api, browser: Browser, frontend_url: str, width: int) -> None:
    api, url = crew_api
    ctx = browser.new_context(locale="cs-CZ", **{**IPHONE, "viewport": {"width": width, "height": 800}})
    page = ctx.new_page()
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector("#otherDays a", timeout=15_000)
    page.wait_for_selector("#otherDepartments", timeout=15_000)
    for selector in ("#tomorrow a", "#otherDays a.day", "#otherDepartments summary"):
        _assert_tap_target(page, selector)
    ctx.close()


def test_history_summary_on_the_day_screen_is_44px(page: Page, frontend_url: str, api_url: str) -> None:
    _connect(page, frontend_url, api_url)
    _create_production(page, f"E2E tap {uuid.uuid4().hex[:6]}")
    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    _assert_tap_target(page, "#historyPanel summary")


def _sign_in_editor(page: Page, api: str) -> None:
    """Only a signed-in editor has the masthead; nothing here needs the API to answer."""
    page.add_init_script(f"localStorage.setItem('filmrunner.editor.connection', JSON.stringify({{apiBase: {api!r}, token: 'test'}}))")


def test_document_language_follows_the_chosen_language_in_viewer_and_editor(crew_api, browser: Browser, frontend_url: str) -> None:
    api, url = crew_api
    ctx = browser.new_context(locale="cs-CZ", service_workers="block")
    page = ctx.new_page()
    _sign_in_editor(page, url)
    for path in ("index.html?demo=1", "editor.html"):
        page.goto(f"{frontend_url}/{path}")
        page.wait_for_selector("#langToggle", timeout=10_000)
        expect(page.locator("html")).to_have_attribute("lang", "cs")
        page.click("#langToggle")
        expect(page.locator("html")).to_have_attribute("lang", "en")
        page.click("#langToggle")
        expect(page.locator("html")).to_have_attribute("lang", "cs")
    ctx.close()


@pytest.mark.parametrize("path", ["index.html", "editor.html"])
def test_viewport_covers_the_notch(path: str) -> None:
    assert "viewport-fit=cover" in (Path(__file__).resolve().parents[1] / path).read_text()


def _newest_chromium(browser_type: BrowserType) -> Path | None:
    pinned = Path(browser_type.executable_path)
    root = next((parent.parent for parent in pinned.parents if parent.name.startswith("chromium-")), None)
    if root is None:
        return None
    found = [*root.glob("chromium-*/chrome-mac*/*.app/Contents/MacOS/*"), *root.glob("chromium-*/chrome-linux*/chrome")]
    return max(found, key=lambda path: int(re.search(r"chromium-(\d+)", str(path)).group(1)), default=None)


@pytest.fixture
def notched(browser_type: BrowserType) -> Iterator[Callable[..., Page]]:
    """Playwright's iPhone profile reports no insets, and its pinned browser has no way to fake them,
    so without a newer build next to it this skips: env(safe-area-inset-*) would just read 0 and prove nothing."""
    executable = _newest_chromium(browser_type)
    if executable is None:
        pytest.skip("no Chromium build installed")
    browser = browser_type.launch(headless=True, executable_path=str(executable), args=["--headless=new"])

    def open_page(*, width: int, height: int, **insets: int) -> Page:
        page = browser.new_context(locale="cs-CZ", **{**IPHONE, "viewport": {"width": width, "height": height}}).new_page()
        try:
            page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": 0, "left": 0, "right": 0, "bottom": 0, **insets}})
        except PlaywrightError:
            pytest.skip(f"{browser.version} cannot fake safe-area insets")
        return page

    yield open_page
    browser.close()


SCREENS = [("index.html?demo=1", "#sheet.visible"), ("editor.html", "#langToggle")]


@pytest.mark.parametrize("path,ready", SCREENS)
def test_nothing_sits_in_a_landscape_notch(crew_api, notched, frontend_url: str, path: str, ready: str) -> None:
    # Narrow enough that the centred column reaches the edges, as on a wide-notched Android phone.
    page = notched(width=660, height=360, left=47, right=47, bottom=21)
    _sign_in_editor(page, crew_api[1])
    page.goto(f"{frontend_url}/{path}")
    page.wait_for_selector(ready, timeout=10_000)
    box = page.evaluate("(() => { const r = document.querySelector('.masthead').getBoundingClientRect(); return [r.left, innerWidth - r.right]; })()")
    assert min(box) >= 47, f"masthead edges {box} reach into the 47px notch"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("path,ready", SCREENS)
def test_nothing_sits_under_a_portrait_notch(crew_api, notched, frontend_url: str, path: str, ready: str) -> None:
    page = notched(width=390, height=844, top=47, bottom=34)
    _sign_in_editor(page, crew_api[1])
    page.goto(f"{frontend_url}/{path}")
    page.wait_for_selector(ready, timeout=10_000)
    top = page.evaluate("document.querySelector('.masthead').getBoundingClientRect().top")
    assert top >= 47, f"masthead starts at {top}px, under the 47px notch"


def test_confirm_bar_clears_the_home_indicator(crew_api, notched, frontend_url: str) -> None:
    api, url = crew_api
    page = notched(width=390, height=844, top=47, bottom=34)
    page.goto(_crew_link(frontend_url, url))
    page.wait_for_selector("#confirmBtn", timeout=15_000)
    bottom = page.evaluate("document.querySelector('#confirmBtn').getBoundingClientRect().bottom")
    assert bottom <= 844 - 34, f"confirm button ends at {bottom}px, inside the 34px home indicator"

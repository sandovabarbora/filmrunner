"""Smoke test for the offline-first call sheet PWA.

Serves the built app (frontend/dist, run `npm run build` first) over a
local static server and checks the shell renders, the service worker
registers, and the URL modes behave. Data loading against the API is
covered by the backend tests; this guards the app shell that must work
with no signal on set.
"""

from pathlib import Path

from playwright.sync_api import Page, expect

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"


def test_root_is_the_entry_page_not_a_form(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    page.wait_for_selector("#openEditor", timeout=10_000)
    assert "FilmRunner" in (page.locator("h1").text_content() or "")
    assert page.locator("#lookup").count() == 0
    assert page.locator("#openEditor").get_attribute("href") == "editor.html"
    page.click("#openDemo")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 7 of 24" in page.locator("#dayLabel").inner_text()


def test_dev_mode_shows_the_lookup_form(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html?dev=1")
    page.wait_for_selector("#loadBtn", timeout=10_000)
    assert page.locator("#loadBtn").is_visible()
    assert not page.locator("#sheet").evaluate("el => el.classList.contains('visible')")


def test_share_link_loads_from_api_without_form(page: Page, frontend_url: str) -> None:
    page.route(
        "**/api/v1/public/call-sheets/abc",
        lambda route: route.fulfill(
            content_type="application/json",
            body='{"unit_name":"Second Unit","day_number":3,"day_count":9,"shoot_date":"2026-10-01",'
            '"current_revision":{"revision_letter":"A","schedule_items":[]}}',
        ),
    )
    page.goto(f"{frontend_url}/index.html?sheet=abc&api=http://api.test")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 3 of 9" in page.locator("#dayLabel").inner_text()
    assert page.locator("#lookup").count() == 0


def test_service_worker_registers(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    registered = page.evaluate(
        "navigator.serviceWorker.ready.then(r => Boolean(r.active || r.installing || r.waiting))"
    )
    assert registered is True


def test_load_without_api_shows_offline_status(page: Page, frontend_url: str) -> None:
    """Failure case: no API and no cache must show a visible status, not a blank sheet."""
    page.goto(f"{frontend_url}/index.html?dev=1")
    page.fill("#apiBase", "http://127.0.0.1:1")
    page.fill("#callSheetId", "00000000-0000-0000-0000-000000000000")
    page.click("#loadBtn")
    page.wait_for_function(
        "document.querySelector('#status').textContent.trim().length > 0", timeout=10_000
    )
    assert page.locator("#status").inner_text().strip() != ""


def test_demo_mode_renders_bundled_call_sheet(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 7 of 24" in page.locator("#dayLabel").inner_text()
    assert page.locator("#scheduleBody tr").count() == 4
    assert page.locator("#revBadgeWrap").inner_text().strip() == "REV B"
    assert page.locator("#lookup").count() == 0
    # The demo is the first thing a prospect sees: it shows every block the sheet has.
    assert page.locator("#locations .location").count() == 2
    assert page.locator("#castTable tbody tr").count() == 3
    assert page.locator("#revChanges li").count() == 3
    assert "replaces A" in page.locator("#revReplaces").inner_text()
    assert page.locator("#cancelledBanner").count() == 0


def test_demo_mode_missing_json_shows_error_not_blank(page: Page, frontend_url: str) -> None:
    """Failure case: if the bundled JSON is unreachable and nothing is cached, say so."""
    page.route("**/demo/call-sheet.json", lambda route: route.abort())
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_function("document.querySelector('#status').textContent.trim().length > 0", timeout=10_000)
    assert "error" in page.locator("#status").get_attribute("class")
    assert not page.locator("#sheet").evaluate("el => el.classList.contains('visible')")


def test_schedule_text_is_not_interpreted_as_html(page: Page, frontend_url: str) -> None:
    """Security: a set note containing markup must render as text (FR-7 finding 2)."""
    page.route(
        "**/demo/call-sheet.json",
        lambda route: route.fulfill(
            content_type="application/json",
            body='{"unit_name":"U","day_number":1,"day_count":1,"shoot_date":"2026-01-01",'
            '"current_revision":{"revision_letter":"A","schedule_items":[{"order_index":1,'
            '"scene_number":"1","int_ext":"INT","day_night":"DAY",'
            '"set_description":"<img src=x onerror=window.__pwned=1>","page_count_eighths":8}]}}',
        ),
    )
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert page.locator("#scheduleBody img").count() == 0
    assert "<img" in page.locator("#scheduleBody").inner_text()
    assert page.evaluate("window.__pwned") is None


def test_contacts_render_with_tap_to_call_and_no_number_fallback(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#contacts", timeout=10_000)
    assert "Eva Dvořáková" in page.locator("#contacts .hod").inner_text()
    tel_links = page.locator("#contacts a.phone")
    assert tel_links.count() >= 5
    assert tel_links.first.get_attribute("href").startswith("tel:+420")
    assert page.locator("#contacts .phone.none").count() == 1  # UPM has no number on file
    assert "Bulovka" in page.locator("#contacts .hospital").inner_text()


def test_contacts_get_whatsapp_and_copy_only_when_the_number_normalises(page: Page, frontend_url: str) -> None:
    """FR-49: every contact card offers call, WhatsApp and copy; a non-numeric phone gets no WhatsApp link."""
    page.route(
        "**/api/v1/public/call-sheets/wa1",
        lambda route: route.fulfill(
            content_type="application/json",
            body=(
                '{"unit_name":"U","day_number":1,"day_count":1,"shoot_date":"2026-01-01",'
                '"current_revision":{"revision_letter":"A","schedule_items":[]},'
                '"contacts":{"head_of_day":null,"nearest_hospital":null,"department_heads":['
                '{"name":"Petr Novak","department":"Grip","position":"Key Grip",'
                '"phone":"777 123 456","email":null,"photo_url":null},'
                '{"name":"Jana Svobodova","department":"Art","position":"Set Dresser",'
                '"phone":"ask Petra","email":null,"photo_url":null}'
                "]}}"
            ),
        ),
    )
    page.goto(f"{frontend_url}/index.html?sheet=wa1&api=http://api.test")
    page.wait_for_selector("#contacts", timeout=10_000)
    rows = page.locator("#contacts .contact")
    assert rows.count() == 2

    petr = rows.filter(has_text="Petr Novak")
    assert petr.locator("a.phone").get_attribute("href").startswith("tel:")
    wa = petr.locator("a.contact-btn.wa")
    assert wa.count() == 1
    assert wa.get_attribute("href").startswith("https://wa.me/420777123456")
    assert petr.locator("button.contact-btn.copy").count() == 1

    jana = rows.filter(has_text="Jana Svobodova")
    assert jana.locator("a.phone").count() == 1  # the tel: link stays; no WhatsApp for unusable text
    assert jana.locator("a.contact-btn.wa").count() == 0
    assert jana.locator("button.contact-btn.copy").count() == 1


_SHEET_BODY = (
    '{"unit_name":"Second Unit","day_number":3,"day_count":9,"shoot_date":"2026-10-01",'
    '"current_revision":{"revision_letter":"A","schedule_items":[]}}'
)


def test_going_offline_after_a_live_load_shows_cached_status_with_timestamp(page: Page, frontend_url: str) -> None:
    """FR-9: the service worker's own cache can answer fetch() when offline,
    which used to read as "Live data". The worker now stamps every response
    with where it came from (vite.config.ts); loader.ts trusts the stamp,
    not whether fetch() merely succeeded.
    """
    page.route(
        "**/api/v1/public/call-sheets/xyz",
        lambda route: route.fulfill(content_type="application/json", body=_SHEET_BODY),
    )
    url = f"{frontend_url}/index.html?sheet=xyz&api=http://api.test"
    page.goto(url)
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert page.locator("#status").get_attribute("class") == "status online"

    # Give the worker's own cache.put() (fired after fetchDidSucceed) a beat
    # to land before we cut the network it would otherwise fall back to.
    page.wait_for_function(
        "caches.open('filmrunner-api-v1').then(c => c.keys()).then(k => k.length > 0)",
        timeout=10_000,
    )

    # Simulate the network being down for this call specifically (not the
    # whole page — the local test server standing in for "no signal on
    # set" would otherwise fail the navigation itself, which isn't what
    # this test is about; the app shell's own offline navigation is served
    # by the precache route, unrelated to this API-freshness check).
    page.unroute("**/api/v1/public/call-sheets/xyz")
    page.route("**/api/v1/public/call-sheets/xyz", lambda route: route.abort())

    page.goto(url)
    page.wait_for_function(
        "document.querySelector('#status').textContent.trim().length > 0", timeout=10_000
    )
    status = page.locator("#status")
    assert status.get_attribute("class") == "status offline"
    assert "Offline" in status.inner_text()
    assert "saved" in status.inner_text()
    assert "Day 3 of 9" in page.locator("#dayLabel").inner_text()


def test_worker_without_the_freshness_stamp_shows_unknown_not_live(page: Page, frontend_url: str) -> None:
    """Failure case: an older service worker (deployed before this stamp
    existed) can still be the one controlling the page after an upgrade,
    since it keeps intercepting fetches until it is replaced. It cannot
    tell live from cached either, so the app must not guess "Live" just
    because fetch() succeeded.

    A fetch a service worker intercepts and re-issues isn't reliably
    routable at the network layer across Playwright versions (registration
    itself and in-worker fetches are separate browser targets from the
    page), so this test avoids interception entirely: it swaps the built
    sw.js on disk for a stub that never stamps, and serves the call sheet
    itself as a same-origin static file the local server (conftest.py)
    answers directly — a real round trip, nothing mocked.
    """
    sw_path = DIST_DIR / "sw.js"
    original_sw = sw_path.read_text()
    stale_sw = (
        "self.addEventListener('install', () => self.skipWaiting());"
        "self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));"
        "self.addEventListener('fetch', (e) => {"
        "  if (e.request.url.includes('/api/v1/public/call-sheets/')) e.respondWith(fetch(e.request));"
        "});"
    )
    sw_path.write_text(stale_sw)

    fixture_path = DIST_DIR / "api" / "v1" / "public" / "call-sheets" / "xyz"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(_SHEET_BODY)

    try:
        page.goto(f"{frontend_url}/index.html?dev=1")
        page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=10_000)

        page.fill("#apiBase", frontend_url)
        page.fill("#callSheetId", "xyz")
        page.click("#loadBtn")

        page.wait_for_selector("#sheet.visible", timeout=10_000)
        status = page.locator("#status")
        assert "Unknown freshness" in status.inner_text()
        assert "Live" not in status.inner_text()
    finally:
        sw_path.write_text(original_sw)
        fixture_path.unlink()


def test_share_link_to_a_missing_or_non_public_sheet_shows_a_clear_message_not_a_spinner(page: Page, frontend_url: str) -> None:
    """FR-11 failure case: a crew link to a call sheet that no longer
    exists (or, once the API has that concept, is not public — both are
    404 today) must say so plainly, never sit on a spinner or claim the
    server "could not be reached" (that phrasing invites a retry that
    can never succeed for a sheet that simply is not there).
    """
    page.route(
        "**/api/v1/public/call-sheets/gone",
        lambda route: route.fulfill(status=404, content_type="application/json", body='{"detail":"Call sheet not found"}'),
    )
    page.goto(f"{frontend_url}/index.html?sheet=gone&api=http://api.test")
    page.wait_for_function(
        "document.querySelector('#status').textContent.trim().length > 0", timeout=10_000
    )
    status = page.locator("#status")
    assert "does not exist" in status.inner_text()
    assert "could not be reached" not in status.inner_text()
    assert page.locator(".skeleton").count() == 0
    assert page.locator("#notFound").is_visible()
    assert not page.locator("#sheet").evaluate("el => el.classList.contains('visible')")


def test_print_media_shows_paper_chrome_and_hides_screen_controls(page: Page, frontend_url: str) -> None:
    """The printed sheet carries its own header line and footer; screen-only controls disappear."""
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    page.emulate_media(media="print")
    assert page.locator("#printFoot").is_visible()
    assert "REV B" in page.locator("#printFoot").inner_text()
    assert not page.locator(".actions").is_visible()
    assert not page.locator("#status").is_visible()
    assert page.locator("#otherDepartments summary").count() == 0 or not page.locator("#otherDepartments summary").is_visible()
    page.emulate_media(media="screen")
    assert not page.locator("#printFoot").is_visible()
    assert page.locator(".actions").is_visible()


def test_czech_browser_gets_a_czech_sheet_and_the_toggle_switches(browser, frontend_url: str) -> None:
    """FR-48: a cs-CZ browser reads the demo sheet in Czech; the toggle flips to English and is remembered."""
    ctx = browser.new_context(locale="cs-CZ", viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "7. den z 24" in page.locator("#dayLabel").inner_text()
    assert page.locator("#dateLabel").inner_text().strip() == "· út 22. 9. 2026"
    assert "REV B nahrazuje A" in page.locator("#revReplaces").inner_text()
    assert page.locator(".calls .label").first.text_content().strip() == "Sraz štábu"  # CSS uppercases it
    assert page.locator("#locations h2").text_content().strip() == "Kde"
    assert page.locator("#contacts h2").text_content().strip() == "Komu volat"
    assert page.locator("#castTable th").first.text_content().strip() == "Herci"
    # user-entered text is never translated
    assert "Riverbank, Troja" in page.locator("#locations").inner_text()
    page.click("#langToggle")
    assert "Day 7 of 24" in page.locator("#dayLabel").inner_text()
    page.reload(); page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert "Day 7 of 24" in page.locator("#dayLabel").inner_text()  # remembered
    assert page.locator("#langToggle").inner_text().strip() == "Čeština"
    ctx.close()


def test_privacy_page_reachable_from_sheet_landing_and_editor(page: Page, frontend_url: str) -> None:
    """FR-59: one tap from the crew's sheet and the landing to what is stored about them; CS/EN."""
    page.goto(f"{frontend_url}/index.html?demo=1")
    page.wait_for_selector("#sheet.visible", timeout=10_000)
    assert page.locator("#privacyLink").get_attribute("href") == "privacy.html"
    page.click("#privacyLink")
    page.wait_for_selector(".privacy", timeout=10_000)
    assert page.locator("body").get_attribute("data-lang") == "en"  # en-US browser
    assert "what FilmRunner stores about you" in page.locator("h1[lang='en']").inner_text()
    assert "Supabase" in page.locator(".privacy").inner_text() and "Anthropic" in page.locator(".privacy").inner_text()
    page.click(".langToggle button[data-lang='cs']")
    assert page.locator("body").get_attribute("data-lang") == "cs"
    assert page.locator("h1[lang='cs']").is_visible() and not page.locator("h1[lang='en']").is_visible()
    page.goto(f"{frontend_url}/landing.html"); page.wait_for_selector("#privacyLink", timeout=10_000)
    assert page.locator("#privacyLink").get_attribute("href") == "privacy.html"


def test_landing_flow_video_autoplays_respects_reduced_motion_and_hides_if_missing(page: Page, frontend_url: str) -> None:
    """FR-54: the recorded flow video plays muted/looped by default, only offers manual
    controls (no autoplay) when the visitor asked for reduced motion, and disappears
    entirely rather than showing a broken player if the file is missing."""
    page.goto(f"{frontend_url}/landing.html")
    video = page.locator("video[data-flow-video]")
    video.wait_for(timeout=10_000)
    assert video.get_attribute("poster") == "landing/call-sheet-top.cs.jpg"  # FR-62: per-language shots
    assert video.get_attribute("src") == "landing/landing-flow.webm"
    page.wait_for_timeout(500)
    assert video.evaluate("el => el.autoplay") is True
    assert video.evaluate("el => el.muted") is True
    assert video.evaluate("el => el.loop") is True
    assert video.evaluate("el => el.paused") is False

    ctx = page.context.browser.new_context(viewport=page.viewport_size, reduced_motion="reduce")
    reduced = ctx.new_page()
    reduced.goto(f"{frontend_url}/landing.html")
    rv = reduced.locator("video[data-flow-video]")
    rv.wait_for(timeout=10_000)
    reduced.wait_for_timeout(500)
    assert rv.evaluate("el => el.autoplay") is False
    assert rv.evaluate("el => el.controls") is True
    assert rv.evaluate("el => el.paused") is True
    ctx.close()

    ctx2 = page.context.browser.new_context(viewport=page.viewport_size)
    missing = ctx2.new_page()
    missing.route("**/landing/landing-flow.webm", lambda route: route.fulfill(status=404, body="not found"))
    missing.goto(f"{frontend_url}/landing.html")
    missing.wait_for_timeout(2_000)
    assert missing.locator("section.flow").count() == 0
    ctx2.close()


def test_landing_shows_the_screenshots_of_the_visitor_s_language(browser, frontend_url: str) -> None:
    """FR-62: a Czech visitor sees the Czech shots (and Czech copy); English sees the English ones; a missing
    file hides only its own image, never the figure the other language still needs."""
    for locale, suffix, other in (("cs-CZ", "cs", "en"), ("en-US", "en", "cs")):
        ctx = browser.new_context(locale=locale, viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(f"{frontend_url}/landing.html")
        page.wait_for_selector(".shots figure", timeout=10_000)
        shown = page.locator(f".shots img[lang='{suffix}']")
        expect(shown).to_have_count(3)
        for i in range(3):
            assert shown.nth(i).is_visible(), f"{locale}: shot {i} hidden"
            assert f".{suffix}.jpg" in shown.nth(i).get_attribute("src")
        assert not page.locator(f".shots img[lang='{other}']").first.is_visible()
        # every shot really loaded (naturalWidth 0 means a broken file)
        widths = page.eval_on_selector_all(f".shots img[lang='{suffix}']", "els => els.map(e => e.naturalWidth)")
        assert all(w > 0 for w in widths), widths
        ctx.close()


def test_landing_survives_a_missing_screenshot(browser, frontend_url: str) -> None:
    """FR-25/FR-62 failure case: one missing file drops that image only; the figure and its caption stay
    as long as the other language's shot is there. The context blocks service workers: the PWA's worker
    serves precached assets without touching the network, so `route` would never see the request
    (the same gap FR-9's offline tests documented)."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    page = ctx.new_page()
    # and no HTTP cache either: a cached copy would be served without a request, so the route
    # would never fire and the test would pass or fail by accident.
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    page.route("**/landing/contacts.en.jpg", lambda route: route.abort())
    page.goto(f"{frontend_url}/landing.html")
    page.wait_for_selector(".shots figure", timeout=10_000)
    expect(page.locator(".shots img[lang='en']")).to_have_count(2, timeout=5_000)
    assert page.locator(".shots figure").count() == 3  # the Czech shot keeps the third figure alive
    assert page.locator(".shots img[lang='cs']").count() == 3
    ctx.close()

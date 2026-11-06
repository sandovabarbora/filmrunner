"""End-to-end: Web Push opt-in from a crew member's personal link (FR-16 dod).

The two browser-native APIs a real push subscription needs (a service
worker registration wired to an actual push service, and the OS asking the
user for permission) cannot be exercised by an automated headless browser
against a live push service — there is no phone to receive the
notification. What *is* real here: our own code (push.ts, NotificationToggle),
a real build, a real uvicorn+Postgres API, and a real browser executing it.
Only `Notification.requestPermission` and `PushManager.subscribe` are
stubbed, via `page.add_init_script` before any app code runs, standing in
for "the user said yes" and "the browser minted a subscription" — the same
narrow substitution FR-18's photo-upload E2E made for a Supabase Storage
server it could not stand up for real.

`docs/research/manual-test-protocol-push-ios.md` covers the part this test
cannot: a real notification arriving on a real phone.
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
E2E_TOKEN = "e2e-push-token"

# A fixed test VAPID public key (not a secret — the private half never leaves
# the API process's env). Any well-formed 65-byte uncompressed-point base64url
# string works, since PushManager.subscribe itself is stubbed in this test.
TEST_VAPID_PUBLIC = "BF444dAIwUN9tiuZ2WfIS3t2b7jQ44J0KdgjuBLR8gd0lBiYB8WarGY2WMcKepATuIdUnBDbM2DiBWqfDWnLcmM"
TEST_VAPID_PRIVATE = "n0HlJAfXvV8jdKodWlfMPG2RM0ajsZmvhBJPMat2SDM"

_STUB_PUSH_API = """
(() => {
  // A real PushManager subscription persists across reloads; this stub's
  // closure state would not, so it is mirrored into localStorage — the
  // stub is re-injected fresh by add_init_script on every navigation.
  const KEY = '__fr_e2e_subscribed';
  const fakeSub = {
    endpoint: 'https://fake-push.example.com/e2e-endpoint',
    toJSON: () => ({ endpoint: 'https://fake-push.example.com/e2e-endpoint', keys: { p256dh: 'fake-p256dh-key', auth: 'fake-auth-key' } }),
    unsubscribe: async () => { localStorage.removeItem(KEY); return true; },
  };
  const registration = {
    pushManager: {
      subscribe: async () => { localStorage.setItem(KEY, '1'); return fakeSub; },
      getSubscription: async () => (localStorage.getItem(KEY) ? fakeSub : null),
    },
  };
  Object.defineProperty(window.navigator, 'serviceWorker', {
    value: { ready: Promise.resolve(registration), register: async () => registration, addEventListener: () => {}, controller: null },
    configurable: true,
  });
  window.Notification = function () {};
  window.Notification.requestPermission = async () => 'granted';
  window.PushManager = function () {};
})();
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def api_url() -> Iterator[str]:
    """Same real-API-and-DB pattern as test_editor_e2e.py, with VAPID keys
    set so the "Enable notifications" control has something to offer."""
    env = {
        **os.environ,
        "FILMRUNNER_DATABASE_URL": TEST_DB_URL,
        "FILMRUNNER_API_BEARER_TOKEN": E2E_TOKEN,
        "FILMRUNNER_ENVIRONMENT": "development",
        "FILMRUNNER_CORS_ORIGINS": "*",
        "FILMRUNNER_VAPID_PUBLIC_KEY": TEST_VAPID_PUBLIC,
        "FILMRUNNER_VAPID_PRIVATE_KEY": TEST_VAPID_PRIVATE,
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


def _publish_a_sheet_with_one_crew_member(page: Page, frontend_url: str, api_url: str) -> str:
    """Returns the crew member's personal link (?sheet=..&api=..&me=..)."""
    page.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#newProduction", timeout=10_000)
    page.fill("#newProduction", f"E2E push {uuid.uuid4().hex[:6]}")
    page.click("#createProduction")
    page.wait_for_selector("#newDay", timeout=10_000)

    page.click("role=tab[name='Crew']")
    page.wait_for_selector("#crewName", timeout=10_000)
    page.fill("#crewName", "Jana Novotná")
    page.fill("#crewDept", "Grip")
    page.fill("#crewPos", "Key grip")
    page.click("#addCrew")
    expect(page.locator("#crew")).to_contain_text("Jana Novotná", timeout=10_000)

    page.click("role=tab[name='Days']")
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:30")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    page.wait_for_selector("#personalLinks", timeout=10_000)
    link = page.locator("#personalLinks li", has_text="Jana Novotná").get_by_role("link", name="Open").get_attribute("href")
    assert link and "&me=" in link
    return link


def test_enabling_and_disabling_notifications_from_a_personal_link(page: Page, frontend_url: str, api_url: str) -> None:
    link = _publish_a_sheet_with_one_crew_member(page, frontend_url, api_url)

    page.add_init_script(_STUB_PUSH_API)
    page.goto(link)
    page.wait_for_selector("#you", timeout=15_000)
    page.wait_for_selector("#notifyToggle", timeout=10_000)
    expect(page.locator("#notifyToggle")).to_contain_text("Notify me")

    page.click("#notifyToggle button")
    expect(page.locator("#notifyToggle")).to_contain_text("Notifications on", timeout=10_000)

    # A fresh load of the same link recognises the existing (stubbed) subscription.
    page.reload()
    page.wait_for_selector("#notifyToggle", timeout=10_000)
    expect(page.locator("#notifyToggle")).to_contain_text("Notifications on")

    page.click("#notifyToggle >> text=Turn off")
    expect(page.locator("#notifyToggle")).to_contain_text("Notify me", timeout=10_000)


def test_rev_replaces_note_only_appears_from_the_second_revision(page: Page, frontend_url: str, api_url: str) -> None:
    """FR-11/FR-16: the sheet itself shows "REV B replaces A" once there is a correction, not on the first publish."""
    page.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )
    page.goto(f"{frontend_url}/editor.html")
    page.wait_for_selector("#newProduction", timeout=10_000)
    page.fill("#newProduction", f"E2E replaces {uuid.uuid4().hex[:6]}")
    page.click("#createProduction")
    page.wait_for_selector("#newDay", timeout=10_000)
    page.click("#newDay")
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "06:00")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    share = page.locator("#shareLink").get_attribute("href")
    assert share

    page.goto(share)
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    assert page.locator("#revReplaces").count() == 0  # REV A: nothing to replace yet

    page.go_back()
    page.wait_for_selector("#general_crew_call", timeout=10_000)
    page.fill("#general_crew_call", "07:00")
    page.click("#publish")
    expect(page.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)

    page.goto(share)
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    expect(page.locator("#revReplaces")).to_contain_text("REV B replaces A")


def test_open_personal_link_tab_picks_up_a_published_revision_without_a_manual_reload(
    page: Page, frontend_url: str, api_url: str
) -> None:
    """FR-130 failure case: a crew member has the sheet open from before the AD
    publishes a correction. Backgrounding the tab (picking up another app) and
    foregrounding it again (checking the phone) must show REV B, not require a
    manual reload — the exact "wrong call time" pain BRIEF.md's Q3 names."""
    editor = page.context.new_page()
    editor.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {E2E_TOKEN!r}}}))"
    )
    editor.goto(f"{frontend_url}/editor.html")
    editor.wait_for_selector("#newProduction", timeout=10_000)
    editor.fill("#newProduction", f"E2E refresh {uuid.uuid4().hex[:6]}")
    editor.click("#createProduction")
    editor.wait_for_selector("#newDay", timeout=10_000)
    editor.click("#newDay")
    editor.wait_for_selector("#general_crew_call", timeout=10_000)
    editor.fill("#general_crew_call", "06:00")
    editor.click("#publish")
    expect(editor.locator("#notice")).to_contain_text("Published REV A", timeout=15_000)
    share = editor.locator("#shareLink").get_attribute("href")
    assert share

    page.goto(share)
    page.wait_for_selector("#sheet.visible", timeout=15_000)
    expect(page.locator("#crewCall")).to_have_text("06:00")
    # FR-221: the worker taking control re-reads once, which would pick up REV B and race the "still REV A" check below.
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=10_000)
    page.wait_for_load_state("networkidle")

    # Publish REV B while the viewer tab sits untouched, exactly like an AD's late-night fix.
    editor.fill("#general_crew_call", "07:15")
    editor.click("#publish")
    expect(editor.locator("#notice")).to_contain_text("Published REV B", timeout=15_000)
    editor.close()

    # Still REV A: nothing has re-fetched yet (this is the regression FR-130 guards).
    expect(page.locator("#crewCall")).to_have_text("06:00")

    # The moment a crew member picks their phone back up, the OS fires a real
    # visibilitychange event as the tab goes from hidden to visible. Headless
    # Chromium does not reliably reproduce the cross-tab "hidden" half of that
    # in this sandbox (bring_to_front() does not flip document.visibilityState
    # here), so this dispatches the same event App.tsx's listener reacts to —
    # exercising the exact fix, not the OS behaviour around it.
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    expect(page.locator("#crewCall")).to_have_text("07:15", timeout=10_000)
    expect(page.locator("#revReplaces")).to_contain_text("REV B replaces A")


def test_confirming_also_turns_on_notifications(page: Page, frontend_url: str, api_url: str) -> None:
    link = _publish_a_sheet_with_one_crew_member(page, frontend_url, api_url)
    page.add_init_script(_STUB_PUSH_API)
    page.goto(link)
    page.wait_for_selector("#confirmPushNote", timeout=15_000)
    expect(page.locator("#confirmAsk")).to_contain_text("Confirm you know")
    page.click("#confirmBtn")
    expect(page.locator("#confirmDone")).to_contain_text("your AD can see", timeout=15_000)
    expect(page.locator("#confirmPushOn")).to_be_visible(timeout=15_000)
    expect(page.locator("#notifyToggle")).to_contain_text("Notifications on", timeout=10_000)


def test_refusing_notifications_never_blocks_confirming(page: Page, frontend_url: str, api_url: str) -> None:
    link = _publish_a_sheet_with_one_crew_member(page, frontend_url, api_url)
    page.add_init_script(_STUB_PUSH_API)
    page.add_init_script("Notification.requestPermission = async () => 'default';")
    page.goto(link)
    page.wait_for_selector("#confirmPushNote", timeout=15_000)
    page.click("#confirmBtn")
    expect(page.locator("#confirmDone")).to_contain_text("your AD can see", timeout=15_000)
    expect(page.locator("#confirmPushEnable")).to_contain_text("Try notifications again", timeout=10_000)

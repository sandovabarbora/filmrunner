"""Take the three landing-page screenshots from a real build of the bundled
demo call sheet (index.html?demo=1, no backend needed).

Usage: run `npm run build` in frontend/ first, then:
    python3 scripts/take_landing_screenshots.py

Writes JPEGs into public/landing/. A shot that fails (missing element, no
Chromium) is skipped rather than written broken or blank — FR-25's own
failure case: the landing page ships without that image slot, never a
placeholder. Re-run after any visual change to the sheet to refresh them.
"""

import http.server
import os
import socketserver
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
OUT_DIR = ROOT / "public" / "landing"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

# (base filename, selector to screenshot, what it shows) — taken once per language (FR-62),
# written as <base>.cs.jpg and <base>.en.jpg; the landing shows the pair matching its toggle.
SHOTS = [
    ("call-sheet-top", "header.sheet-header", "the sheet header: production, day, REV badge"),
    ("locations", "#locations", "the Where block: address, parking, hospital, maps link"),
    ("contacts", "#contacts", "Who to call: head of day and department heads, tap-to-call"),
]
LOCALES = [("cs", "cs-CZ"), ("en", "en-US")]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # noqa: D102
        pass


def main() -> int:
    if not (DIST_DIR / "index.html").exists():
        print("dist/index.html missing — run `npm run build` first", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    handler = partial(_QuietHandler, directory=str(DIST_DIR))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    written = []
    try:
        with sync_playwright() as pw:
            # headless=True would add this Chromium build's removed "--headless=old"
            # flag; pass the new headless mode explicitly instead (same workaround
            # prior shifts used against this sandbox's pinned Chromium revision).
            # The cloud sandbox has only a pinned Chromium at CHROMIUM_PATH (and no system fonts, so its
            # shots look rough); on a Mac use Playwright's own browser and the real system fonts.
            if os.path.exists(CHROMIUM_PATH):
                browser = pw.chromium.launch(executable_path=CHROMIUM_PATH, headless=False, args=["--headless=new"])
            else:
                browser = pw.chromium.launch(headless=True)
            for suffix, locale in LOCALES:
                context = browser.new_context(viewport={"width": 390, "height": 844}, locale=locale)
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{port}/index.html?demo=1", wait_until="networkidle")
                page.wait_for_selector("#sheet.visible", timeout=10_000)
                _shoot(page, suffix, written)
                context.close()
            browser.close()
    finally:
        server.shutdown()

    for base, _selector, what in SHOTS:
        for suffix, _locale in LOCALES:
            filename = f"{base}.{suffix}.jpg"
            path = OUT_DIR / filename
            if filename in written:
                print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB) — {what} [{suffix}]")
            else:
                print(f"not written: {path} — {what} [{suffix}]", file=sys.stderr)

    return 0 if written else 1


def _shoot(page, suffix: str, written: list[str]) -> None:
    """The three shots for one language; a missed one never stops the others."""
    if True:
            try:
                # "At a glance" hero shot: header through the sunrise/weather
                # strip, as one clipped region rather than a single element,
                # since those are separate sibling <section>s.
                top = page.locator("header.sheet-header").bounding_box()
                bottom = page.locator("section.meta").bounding_box()
                if top and bottom:
                    page.screenshot(
                        path=str(OUT_DIR / f"call-sheet-top.{suffix}.jpg"),
                        type="jpeg",
                        quality=82,
                        clip={
                            "x": 0,
                            "y": top["y"],
                            "width": page.viewport_size["width"],
                            "height": (bottom["y"] + bottom["height"]) - top["y"],
                        },
                    )
                    written.append(f"call-sheet-top.{suffix}.jpg")
            except Exception as exc:  # noqa: BLE001 - a missed shot must not fail the others
                print(f"skipped call-sheet-top.{suffix}.jpg: {exc}", file=sys.stderr)

            for base, selector, _what in SHOTS[1:]:
                filename = f"{base}.{suffix}.jpg"
                try:
                    page.locator(selector).first.screenshot(
                        path=str(OUT_DIR / filename), type="jpeg", quality=82
                    )
                    written.append(filename)
                except Exception as exc:  # noqa: BLE001 - a missed shot must not fail the others
                    print(f"skipped {filename} ({selector}): {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

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

# (output filename, selector to screenshot, what it shows)
SHOTS = [
    ("call-sheet-top.jpg", "header.sheet-header", "the sheet header: production, day, REV badge"),
    ("locations.jpg", "#locations", "the Where block: address, parking, hospital, maps link"),
    ("contacts.jpg", "#contacts", "Who to call: head of day and department heads, tap-to-call"),
]


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
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(f"http://127.0.0.1:{port}/index.html?demo=1", wait_until="networkidle")
            page.wait_for_selector("#sheet.visible", timeout=10_000)

            try:
                # "At a glance" hero shot: header through the sunrise/weather
                # strip, as one clipped region rather than a single element,
                # since those are separate sibling <section>s.
                top = page.locator("header.sheet-header").bounding_box()
                bottom = page.locator("section.meta").bounding_box()
                if top and bottom:
                    page.screenshot(
                        path=str(OUT_DIR / "call-sheet-top.jpg"),
                        type="jpeg",
                        quality=82,
                        clip={
                            "x": 0,
                            "y": top["y"],
                            "width": page.viewport_size["width"],
                            "height": (bottom["y"] + bottom["height"]) - top["y"],
                        },
                    )
                    written.append("call-sheet-top.jpg")
            except Exception as exc:  # noqa: BLE001 - a missed shot must not fail the others
                print(f"skipped call-sheet-top.jpg: {exc}", file=sys.stderr)

            for filename, selector, _what in SHOTS[1:]:
                try:
                    page.locator(selector).first.screenshot(
                        path=str(OUT_DIR / filename), type="jpeg", quality=82
                    )
                    written.append(filename)
                except Exception as exc:  # noqa: BLE001 - a missed shot must not fail the others
                    print(f"skipped {filename} ({selector}): {exc}", file=sys.stderr)
            browser.close()
    finally:
        server.shutdown()

    for filename, _selector, what in SHOTS:
        path = OUT_DIR / filename
        if filename in written:
            size_kb = path.stat().st_size / 1024
            print(f"wrote {path} ({size_kb:.0f} KB) — {what}")
        else:
            print(f"not written: {path} — {what}", file=sys.stderr)

    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())

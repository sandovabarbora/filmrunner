"""Take the three landing-page screenshots from a real build of the bundled
demo call sheet (index.html?demo=1, no backend needed).

Usage: run `npm run build` in frontend/ first, then:
    python3 scripts/take_landing_screenshots.py

Writes JPEGs into public/landing/. A shot that fails (missing element, no
Chromium) is skipped rather than written broken or blank — FR-25's own
failure case: the landing page ships without that image slot, never a
placeholder. Re-run after any visual change to the sheet to refresh them.

Also rewrites each written image's `width`/`height` attributes in
`landing.html` to its actual captured pixel size (FR-92): the crops this
script takes are not a fixed 390x220 — the header clip and the `#locations`/
`#contacts` element screenshots are each a different real height, and
`landing.html` previously hardcoded a single guessed 390x220 for all six,
which mismatched every one of them (390x391, 350x882, 350x377 among them)
and was Lighthouse's biggest cumulative-layout-shift culprit on the page:
the browser reserved a box at the declared ratio, then reflowed once the
real image loaded. `.shots img { width: 100%; height: auto }` in
landing.css derives its aspect ratio from these attributes, so keeping them
accurate here is what keeps that reservation correct on every re-run.
"""

import http.server
import os
import re
import socketserver
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
OUT_DIR = ROOT / "public" / "landing"
LANDING_HTML = ROOT / "landing.html"
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
    dims: dict[str, tuple[int, int]] = {}
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
                # device_scale_factor stays 1 (default): tried 2 to close
                # Lighthouse's `image-size-responsive` low-resolution finding
                # (FR-92) — it did (best-practices 96 -> 100), but roughly
                # doubling every screenshot's file size pushed Performance
                # from 97 to 88 (LCP moved from an orange 90 to a red 59), a
                # worse regression than the one-point cosmetic gain it bought.
                # Reverted; the low-resolution finding is left as a known,
                # accepted gap (see docs/research/pilot-scale-2026-09.md).
                context = browser.new_context(viewport={"width": 390, "height": 844}, locale=locale)
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{port}/index.html?demo=1", wait_until="networkidle")
                page.wait_for_selector("#sheet.visible", timeout=10_000)
                _shoot(page, suffix, written, dims)
                context.close()
            browser.close()
    finally:
        server.shutdown()

    for base, _selector, what in SHOTS:
        for suffix, _locale in LOCALES:
            filename = f"{base}.{suffix}.jpg"
            path = OUT_DIR / filename
            if filename in written:
                print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB) — {what} [{suffix}], {dims[filename][0]}x{dims[filename][1]}")
            else:
                print(f"not written: {path} — {what} [{suffix}]", file=sys.stderr)

    if dims:
        _update_landing_html_dimensions(dims)

    return 0 if written else 1


def _shoot(page, suffix: str, written: list[str], dims: dict[str, tuple[int, int]]) -> None:
    """The three shots for one language; a missed one never stops the others."""
    if True:
            try:
                # "At a glance" hero shot: header through the sunrise/weather
                # strip, as one clipped region rather than a single element,
                # since those are separate sibling <section>s.
                top = page.locator("header.sheet-header").bounding_box()
                bottom = page.locator("section.meta").bounding_box()
                if top and bottom:
                    width = page.viewport_size["width"]
                    height = (bottom["y"] + bottom["height"]) - top["y"]
                    page.screenshot(
                        path=str(OUT_DIR / f"call-sheet-top.{suffix}.jpg"),
                        type="jpeg",
                        quality=82,
                        clip={"x": 0, "y": top["y"], "width": width, "height": height},
                    )
                    filename = f"call-sheet-top.{suffix}.jpg"
                    written.append(filename)
                    dims[filename] = (round(width), round(height))
            except Exception as exc:  # noqa: BLE001 - a missed shot must not fail the others
                print(f"skipped call-sheet-top.{suffix}.jpg: {exc}", file=sys.stderr)

            for base, selector, _what in SHOTS[1:]:
                filename = f"{base}.{suffix}.jpg"
                try:
                    box = page.locator(selector).first.bounding_box()
                    page.locator(selector).first.screenshot(
                        path=str(OUT_DIR / filename), type="jpeg", quality=82
                    )
                    written.append(filename)
                    if box:
                        dims[filename] = (round(box["width"]), round(box["height"]))
                except Exception as exc:  # noqa: BLE001 - a missed shot must not fail the others
                    print(f"skipped {filename} ({selector}): {exc}", file=sys.stderr)


def _update_landing_html_dimensions(dims: dict[str, tuple[int, int]]) -> None:
    """Rewrite each `<img src="landing/<filename>" ...>` tag's width/height
    attributes in landing.html to match what was actually captured, so a
    stale hardcoded guess can never drift from the real file again (FR-92)."""
    html = LANDING_HTML.read_text()
    changed = []
    for filename, (width, height) in dims.items():
        pattern = re.compile(
            r'(<img\b[^>]*\bsrc="landing/' + re.escape(filename) + r'"[^>]*?)\bwidth="\d+"([^>]*?)\bheight="\d+"'
        )
        new_html, n = pattern.subn(rf'\g<1>width="{width}"\g<2>height="{height}"', html)
        if n == 0:
            print(f"warning: no width/height attributes found for landing/{filename} in {LANDING_HTML.name}", file=sys.stderr)
        elif new_html != html:
            changed.append(f"landing/{filename} -> {width}x{height}")
        html = new_html
    if changed:
        LANDING_HTML.write_text(html)
        print(f"updated {LANDING_HTML.name} image dimensions:")
        for line in changed:
            print(f"  {line}")


if __name__ == "__main__":
    raise SystemExit(main())

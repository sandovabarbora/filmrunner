"""Take the landing page's product shots from the deployed test environment, whose data is all invented.

Usage: python3 scripts/take_landing_screenshots.py [site base URL]

Writes public/landing/<shot>.<lang>.webp. Opens one test session per language, which the
public endpoint rate limits, so run it once. Needs `cwebp` on the PATH. Re-run after a visual
change to these screens has been deployed.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT_DIR = Path(__file__).resolve().parents[1] / "public" / "landing"
DEFAULT_BASE = "https://sandovabarbora.github.io/filmrunner/"
LOCALES = [("cs", "cs-CZ"), ("en", "en-US")]
VIEWPORT = {"width": 390, "height": 844}
PRINT_VIEWPORT = {"width": 794, "height": 900}
# The tester's bar says which persona is showing; it is not part of the product a visitor is being shown.
HIDE_TEST_BAR = "#sandboxBar, .sandbox-bar { display: none !important; }"
# (shot, persona, what to tap after entering, what must be on screen before the picture is taken)
SHOTS = [
    ("crew", "gaffer", None, "#confirmBtn"),
    ("ad", "ad", "#dashItems a", "#seenPanel"),
    ("production", "produkcni", None, "#dashboard"),
]


def enter(page: Page, base: str, persona: str, tap: str | None, ready: str) -> None:
    page.goto(f"{base}editor.html#/test")
    page.wait_for_selector(f'[data-persona="{persona}"]', timeout=60_000)
    page.click(f'[data-persona="{persona}"]')
    if tap:
        page.locator(tap).first.click(timeout=60_000)
    page.wait_for_selector(ready, timeout=60_000)
    page.wait_for_load_state("networkidle")
    page.add_style_tag(content=HIDE_TEST_BAR)
    page.wait_for_timeout(1_000)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(headless=True)
        for lang, locale in LOCALES:
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2, locale=locale, service_workers="block", has_touch=True, is_mobile=True)
            page = ctx.new_page()
            for shot, persona, tap, ready in SHOTS:
                png = Path(tmp) / f"{shot}.{lang}.png"
                enter(page, base, persona, tap, ready)
                page.screenshot(path=str(png))
                subprocess.run(["cwebp", "-quiet", "-q", "78", str(png), "-o", str(OUT_DIR / f"{shot}.{lang}.webp")], check=True)
                print("wrote", shot, lang)
            enter(page, base, "gaffer", None, "#confirmBtn")
            page.set_viewport_size(PRINT_VIEWPORT)
            page.emulate_media(media="print")
            png = Path(tmp) / f"print.{lang}.png"
            page.screenshot(path=str(png))
            subprocess.run(["cwebp", "-quiet", "-q", "78", str(png), "-o", str(OUT_DIR / f"print.{lang}.webp")], check=True)
            ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

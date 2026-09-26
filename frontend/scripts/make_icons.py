"""Render the app icon PNGs from public/icon.svg and public/icon-square.svg.

Usage (from frontend/): python3 scripts/make_icons.py

icon.svg is the rounded icon (favicon, manifest "any"); icon-square.svg is the same drawing full-bleed,
for iOS home screens and Android "maskable" icons, which cut their own shape. Re-run after editing either SVG.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

PUBLIC = Path(__file__).resolve().parents[1] / "public"

# (source svg, output png, size in px)
OUTPUTS = [
    ("icon.svg", "icon.png", 48),
    ("icon.svg", "icon-192.png", 192),
    ("icon.svg", "icon-512.png", 512),
    ("icon-square.svg", "icon-maskable-512.png", 512),
    ("icon-square.svg", "apple-touch-icon.png", 180),
]


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for source, target, size in OUTPUTS:
            page = browser.new_page(viewport={"width": size, "height": size})
            svg = (PUBLIC / source).read_text()
            page.set_content(f'<body style="margin:0">{svg.replace("<svg ", f"<svg width=\"{size}\" height=\"{size}\" ", 1)}</body>')
            page.screenshot(path=str(PUBLIC / target), omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
            page.close()
            print(f"wrote public/{target} ({size}px)")
        browser.close()


if __name__ == "__main__":
    main()

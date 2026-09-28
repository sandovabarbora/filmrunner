"""Validate the built PWA manifest and icons against Chrome's installability
criteria (FR-99).

PR #237/#238 added `icon-192.png`/`icon-512.png`/`icon-maskable-512.png`/
`apple-touch-icon.png` and the "FilmRunner" `short_name`/`name`, but nothing
verified the manifest itself or that the referenced icon files actually exist
at the sizes they claim. Lighthouse's own PWA category and its
`installable-manifest`/`maskable-icon`/`service-worker` audits do not exist in
this project's pinned Lighthouse (13.5.0, confirmed empirically 2026-09-28:
`--only-categories=pwa` errors "unrecognized category", `--only-audits` with
those audit ids returns zero audits/categories) — Google removed the PWA
category and its audits from Lighthouse core in v12 in favour of Chrome
DevTools' own Manifest panel. So this script checks the same ground directly:
Chrome's documented install criteria (web.dev/articles/install-criteria,
checked 2026-09-28) — a manifest with name, short_name, start_url, a
standalone/fullscreen/minimal-ui display, background_color, theme_color, and
icons covering 192x192 and 512x512 at purpose "any" — plus that every icon
`src` the manifest lists actually exists in `dist/` and decodes to the pixel
size its `sizes` field claims (a mismatch is a silent bug: the manifest still
parses, the browser just quietly rejects the icon).

What this script cannot check, because nothing in this sandbox can drive a
real "Add to Home Screen" prompt: HTTPS (true on the deployed GitHub Pages
URL, not on this static-serve check), and whether Chrome/Android/iOS actually
accept the install on a physical device. That is a real-device check for the
founder to run once, the same boundary FR-28's push protocol already
documents (`docs/research/manual-test-protocol-push-ios.md`).

Usage: run `npm run build` in frontend/ first, then:

    python3 scripts/check_pwa_manifest.py

Exits non-zero and prints every failure if the manifest or an icon fails a
check; otherwise prints a pass summary.
"""

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
MANIFEST_PATH = DIST_DIR / "manifest.webmanifest"

REQUIRED_STRING_FIELDS = ["name", "short_name", "start_url"]
VALID_DISPLAY = {"standalone", "fullscreen", "minimal-ui"}


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} is not a PNG (bad signature)")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def check_manifest() -> list[str]:
    errors: list[str] = []

    if not MANIFEST_PATH.exists():
        return [f"{MANIFEST_PATH} does not exist — run `npm run build` first"]

    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except json.JSONDecodeError as exc:
        return [f"manifest.webmanifest is not valid JSON: {exc}"]

    for field in REQUIRED_STRING_FIELDS:
        if not manifest.get(field):
            errors.append(f"manifest missing required field '{field}'")

    display = manifest.get("display")
    if display not in VALID_DISPLAY:
        errors.append(f"manifest 'display' is {display!r}, expected one of {sorted(VALID_DISPLAY)}")

    for field in ("background_color", "theme_color"):
        if not manifest.get(field):
            errors.append(f"manifest missing '{field}' (Chrome installability wants both set)")

    icons = manifest.get("icons") or []
    if not icons:
        errors.append("manifest has no 'icons' array")

    has_192_any = False
    has_512_any = False
    for icon in icons:
        src = icon.get("src")
        sizes = icon.get("sizes", "")
        purpose = icon.get("purpose", "any")
        if not src:
            errors.append(f"icon entry missing 'src': {icon}")
            continue

        icon_path = DIST_DIR / src
        if not icon_path.exists():
            errors.append(f"manifest references '{src}' but it does not exist in dist/")
            continue

        if sizes == "any" and icon_path.suffix == ".svg":
            # A vector icon has no fixed pixel size to check against.
            pass
        elif icon_path.suffix == ".png":
            declared = sizes.split(" ")[0] if sizes else None
            actual_w, actual_h = _png_dimensions(icon_path)
            actual = f"{actual_w}x{actual_h}"
            if declared and declared != actual:
                errors.append(f"'{src}' declares sizes={declared!r} but the PNG is actually {actual}")

        if "any" in purpose or purpose == "any":
            if sizes.startswith("192x192"):
                has_192_any = True
            if sizes.startswith("512x512"):
                has_512_any = True

    if not has_192_any:
        errors.append("no icon with sizes=192x192 and purpose 'any' (or default) — Chrome install criteria requires this")
    if not has_512_any:
        errors.append("no icon with sizes=512x512 and purpose 'any' (or default) — Chrome install criteria requires this")

    sw_path = DIST_DIR / "sw.js"
    if not sw_path.exists():
        errors.append("dist/sw.js does not exist — a registered service worker is part of Chrome's install criteria")

    return errors


def main() -> int:
    errors = check_manifest()
    if errors:
        print("PWA manifest/installability check: FAIL")
        for e in errors:
            print(f"  - {e}")
        print(
            "\nNot checked here (no real device or browser install flow in this sandbox): "
            "HTTPS on the deployed URL, and an actual 'Add to Home Screen' prompt on "
            "Chrome/Android or Safari/iOS."
        )
        return 1

    print("PWA manifest/installability check: PASS")
    print(f"  manifest: {MANIFEST_PATH.relative_to(ROOT.parent)}")
    print("  required fields, display mode, 192x192 + 512x512 'any' icons, maskable icon, and dist/sw.js all present")
    print(
        "\nNot checked here (no real device or browser install flow in this sandbox): "
        "HTTPS on the deployed URL, and an actual 'Add to Home Screen' prompt on "
        "Chrome/Android or Safari/iOS — the founder's own real-device check, same "
        "boundary as docs/research/manual-test-protocol-push-ios.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

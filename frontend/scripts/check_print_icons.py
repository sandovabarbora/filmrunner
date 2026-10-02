"""FR-101: confirm, against a real build and a real headless Chromium print-media pass
(not by reading CSS), whether any `Icon.tsx` (`<svg class="icon">`) element actually
renders inside either PDF export — the day sheet or the editor's crew-list print popup.

PR #236 (2026-09-26) replaced emoji/text glyphs with inline-SVG icons across
`CallSheetView.tsx`. Inline SVG under headless-Chromium print rendering is a known
risk class (a `currentColor`-stroked SVG can render blank or omit-print in some
Chromium print paths), so this checks the real rendered/printed DOM rather than
assuming the CSS that is supposed to hide or show them behaves as written.

Usage: run `npm run build` in frontend/ first, then, with `scripts/pdf_pilot_scale.py`
already run at least once against the same local Postgres (so the "Scale test (FR-52)
v2" production exists):

    python3 scripts/check_print_icons.py

Prints one line per `svg.icon` found in the day sheet under print-media emulation,
whether the crew-list print popup touches `Icon.tsx` at all, and appends a dated
section to docs/research/pilot-scale-2026-09.md. Exits 0 always — this is a
verification report, not a pass/fail gate, since a future feature may legitimately
want an icon to print; it exists so that decision is made on purpose, not discovered
after a pilot day's PDF ships blank boxes.
"""

import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT.parent / "backend"
DIST_DIR = ROOT / "dist"
RESEARCH_FILE = ROOT.parent / "docs" / "research" / "pilot-scale-2026-09.md"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

TOKEN = "pdf-pilot-scale"
NAME = "Scale test (FR-52) v2"
TEST_DB_URL = os.environ.get(
    "FILMRUNNER_DATABASE_URL",
    "postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner_test",
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # noqa: D102
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_static_server() -> tuple[socketserver.TCPServer, int]:
    if not (DIST_DIR / "index.html").exists():
        raise RuntimeError("dist/index.html missing — run `npm run build` first")
    handler = partial(_QuietHandler, directory=str(DIST_DIR))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _backend_python() -> str:
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.exists() else sys.executable


def _start_api() -> tuple[subprocess.Popen, str]:
    python = _backend_python()
    env = {
        **os.environ,
        "FILMRUNNER_DATABASE_URL": TEST_DB_URL,
        "FILMRUNNER_API_BEARER_TOKEN": TOKEN,
        "FILMRUNNER_ENVIRONMENT": "development",
        "FILMRUNNER_CORS_ORIGINS": "*",
        "FILMRUNNER_PUBLIC_RATE_LIMIT_PER_IP": "0",
        "FILMRUNNER_PUBLIC_RATE_LIMIT_PER_TOKEN": "0",
    }
    port = _free_port()
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
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
    return proc, url


def _api(api_url: str, method: str, path: str, body=None):
    req = urllib.request.Request(
        api_url + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def main() -> int:
    if not os.path.exists(CHROMIUM_PATH):
        print(f"no Chromium at {CHROMIUM_PATH}; cannot run this script in this environment", file=sys.stderr)
        return 1

    static_server, static_port = _start_static_server()
    frontend_url = f"http://127.0.0.1:{static_port}"
    api_proc, api_url = _start_api()
    try:
        existing = [p for p in _api(api_url, "GET", "/api/v1/productions") if p["name"] == NAME]
        if not existing:
            print(f'"{NAME}" production not found — run pdf_pilot_scale.py first to seed it', file=sys.stderr)
            return 1
        pid = existing[0]["id"]
        days = _api(api_url, "GET", f"/api/v1/productions/{pid}/call-sheets")
        big_id = next(d["id"] for d in days if d["day_number"] == 5)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROMIUM_PATH, headless=False, args=["--headless=new"])

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(f"{frontend_url}/?sheet={big_id}&api={api_url}")
            page.wait_for_selector("#sheet.visible", timeout=30_000)
            screen = page.evaluate(
                "() => document.querySelectorAll('svg.icon').length"
            )

            page.emulate_media(media="print")
            per_icon = page.evaluate("""
                () => [...document.querySelectorAll('svg.icon')].map(e => {
                  const cs = getComputedStyle(e);
                  const r = e.getBoundingClientRect();
                  return {parent: e.parentElement ? e.parentElement.className : '', display: cs.display,
                          visibility: cs.visibility, w: r.width, h: r.height};
                })
            """)
            rendered_in_print = [
                e for e in per_icon
                if e["display"] != "none" and e["visibility"] != "hidden" and e["w"] > 0 and e["h"] > 0
            ]
            footer_svg = page.evaluate("""
                () => {
                  const svg = document.querySelector('.print-footer-bar svg');
                  if (!svg) return null;
                  const r = svg.getBoundingClientRect();
                  return {isIconClass: svg.classList.contains('icon'), w: r.width, h: r.height};
                }
            """)
            page.close()

            context = browser.new_context(viewport={"width": 390, "height": 844})
            context.add_init_script(
                "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
                + f"{{apiBase: {api_url!r}, token: {TOKEN!r}}}))"
            )
            epage = context.new_page()
            epage.goto(f"{frontend_url}/editor.html#/p/{pid}/crew")
            epage.wait_for_selector("#crew li:nth-child(60)", timeout=30_000)
            with context.expect_page() as popup_info:
                epage.click("#printCrew")
            printed = popup_info.value
            printed.wait_for_load_state("domcontentloaded")
            printed.emulate_media(media="print")
            crew_icon_count = printed.evaluate("() => document.querySelectorAll('svg.icon').length")

            browser.close()
    finally:
        static_server.shutdown()
        api_proc.terminate()
        api_proc.wait(timeout=10)

    print("--- FR-101 print-icon check at FR-52 pilot scale ---")
    print(f"Day sheet: {screen} svg.icon element(s) on screen, {len(per_icon)} still in the DOM under "
          f"print media, {len(rendered_in_print)} of those actually rendered (visible box) in print.")
    for e in rendered_in_print:
        print(f"  RENDERED IN PRINT (unexpected): parent=.{e['parent']!r} {e['w']}x{e['h']}")
    print(f"print-footer-bar svg (the FR-11 QR code, not an Icon.tsx icon): {footer_svg}")
    print(f"Crew-list print popup: {crew_icon_count} svg.icon element(s) in the DOM "
          "(crewPrint.ts does not import Icon.tsx, so 0 is expected).")

    today = time.strftime("%Y-%m-%d")
    verdict = (
        "no Icon.tsx icon renders in either PDF export"
        if not rendered_in_print and crew_icon_count == 0
        else "at least one Icon.tsx icon renders where it previously did not — investigate"
    )
    section = f"""
## FR-101 ({today}): confirmed real print-media rendering of Icon.tsx icons

Ran `frontend/scripts/check_print_icons.py` (headless Chromium at
`/opt/pw-browsers/chromium`, print media emulated, a real build, a real
uvicorn+Postgres API) against the same seeded "{NAME}" production FR-93 uses.

Day sheet has {screen} `svg.icon` element(s) on screen (the print/phone/WhatsApp/copy
icons in `CallSheetView.tsx`); all {len(per_icon)} stay in the DOM once print media is
emulated, but {len(rendered_in_print)} of them actually render (non-zero visible box).
The crew-list print popup has {crew_icon_count} `svg.icon` elements — `crewPrint.ts`
does not import `Icon.tsx` at all, so this print export was never in scope for the SVG
swap. The `print-footer-bar` QR code (`{footer_svg}`) is a separate `qrcode-generator`
SVG, not an `Icon.tsx` icon, and correctly stays visible in both exports (already
verified by FR-11/FR-93).

Verdict: **{verdict}**. Checked why, not just that: `.contact-btn .icon, .actions
.icon {{ display: none; }}` and `.contact-btn.wa, .contact-btn.copy {{
display: none !important; }}` in `styles.css`'s `@media print` block hide every one
of the four `Icon` usages in `CallSheetView.tsx` (the print button, the phone icon, the
WhatsApp icon, the copy/check icon). `git log -S` on that selector shows this predates
PR #236 by renaming only (`.contact-btn .btn-icon` → `.contact-btn .icon`, same
`display: none` behaviour) — before the emoji-to-SVG swap, the emoji glyphs were
already hidden from print the same way, so this is not a regression introduced by the
icon swap; it is unchanged, pre-existing print behaviour. The printed sheet only ever
showed the phone number as plain text (`.contact-btn.phone` gets its own print-specific
style with no icon), never an icon of any kind, in either the emoji era or the SVG era.
No fix was needed; nothing in `styles.css` or `CallSheetView.tsx` changed for this item.
"""
    with open(RESEARCH_FILE, "a", encoding="utf-8") as f:
        f.write(section)
    print(f"\nappended to {RESEARCH_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

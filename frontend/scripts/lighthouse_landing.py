"""Lighthouse mobile score for landing.html, the page a prospective AD or
founder opens first (FR-92).

FR-71's Lighthouse run (and every fix since, FR-77/80/81/82/84) only ever
scored `index.html`, the public call-sheet page — `landing.html` (FR-25/62,
built from FR-6's positioning) has never been scored on its own. Unlike the
sheet, the landing page needs no API or database: it is fully static, so
this script only builds and serves `dist/`, no backend process.

Usage: run `npm run build` in frontend/ first, then:

    python3 scripts/lighthouse_landing.py

Prints the four category scores and any audit Lighthouse itself flags red
(score < 0.5) or orange (< 0.9), and writes
`docs/research/lighthouse-landing.json` (the full report). Chrome is the
sandbox's own pre-installed Chromium (CHROME_PATH), same pattern
`lighthouse_pilot_scale.py` uses.
"""

import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
RESEARCH_DIR = ROOT.parent / "docs" / "research"
REPORT_PATH = RESEARCH_DIR / "lighthouse-landing.json"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # noqa: D102
        pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_static_server() -> tuple[socketserver.TCPServer, int]:
    if not (DIST_DIR / "landing.html").exists():
        raise RuntimeError("dist/landing.html missing — run `npm run build` first")
    handler = partial(_QuietHandler, directory=str(DIST_DIR))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _run_lighthouse(url: str) -> dict:
    env = {**os.environ, "CHROME_PATH": CHROMIUM_PATH}
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "npx", "--yes", "lighthouse", url,
            "--output=json", f"--output-path={REPORT_PATH}",
            "--chrome-flags=--headless=new --no-sandbox",
            "--form-factor=mobile",
            "--only-categories=performance,accessibility,best-practices,seo",
            "--quiet",
        ],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"lighthouse exited {result.returncode}\nstdout: {result.stdout[-3000:]}\nstderr: {result.stderr[-3000:]}")
    return json.loads(REPORT_PATH.read_text())


def main() -> int:
    if not os.path.exists(CHROMIUM_PATH):
        print(f"no Chromium at {CHROMIUM_PATH}; cannot run Lighthouse in this environment", file=sys.stderr)
        return 1

    static_server, static_port = _start_static_server()
    try:
        landing_url = f"http://127.0.0.1:{static_port}/landing.html"
        report = _run_lighthouse(landing_url)
    finally:
        static_server.shutdown()

    scores = {cat: round(data["score"] * 100) for cat, data in report["categories"].items()}
    red_audits = [
        (aid, a["title"], a["score"]) for aid, a in report["audits"].items()
        if a.get("score") is not None and a["scoreDisplayMode"] == "numeric" and a["score"] < 0.5
    ]
    orange_audits = [
        (aid, a["title"], a["score"]) for aid, a in report["audits"].items()
        if a.get("score") is not None and a["scoreDisplayMode"] == "numeric" and 0.5 <= a["score"] < 0.9
    ]

    print("--- Lighthouse, mobile, landing.html ---")
    for cat, score in scores.items():
        print(f"  {cat:<16} {score}")
    if red_audits:
        print("  red audits (score < 0.5):")
        for aid, title, score in red_audits:
            print(f"    {aid:<40} {title:<50} {round(score * 100)}")
    else:
        print("  no red audits")
    if orange_audits:
        print("  orange audits (0.5 <= score < 0.9):")
        for aid, title, score in orange_audits:
            print(f"    {aid:<40} {title:<50} {round(score * 100)}")

    print(f"\nwrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

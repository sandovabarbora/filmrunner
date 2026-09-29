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
`docs/research/lighthouse-landing.json` (the full report). Chrome is this dev
sandbox's own pre-installed Chromium when present, else whatever
`playwright install chromium` put on the machine — same pattern
`lighthouse_pilot_scale.py` uses.

FR-103 (2026-09-29): wired into `.github/workflows/ci.yml` on every PR, same
baseline-check contract as `lighthouse_pilot_scale.py` against
`docs/research/ci-baseline.json`.
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
BASELINE_PATH = RESEARCH_DIR / "ci-baseline.json"
BASELINE_KEY = "lighthouse_landing"
SANDBOX_CHROMIUM_PATH = "/opt/pw-browsers/chromium"
# landing.html is fully static (no API timing involved), so its historical runs show far
# less Performance noise than the public sheet's — still, keep a tolerance band rather than
# an exact match, since it is still a Lighthouse timing metric on a shared CI machine.
PERFORMANCE_NOISE_TOLERANCE = 10
# Same "good" line FR-92/FR-97 already cite for this page's own screenshot-driven CLS fix.
CLS_GOOD_THRESHOLD = 0.1


def _chromium_path() -> str:
    if os.path.exists(SANDBOX_CHROMIUM_PATH):
        return SANDBOX_CHROMIUM_PATH
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        return pw.chromium.executable_path


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
    env = {**os.environ, "CHROME_PATH": _chromium_path()}
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


def _check_baseline(scores: dict, cls: float | None) -> list[str]:
    """Same contract as lighthouse_pilot_scale.py's own check, against this script's
    own key in the shared docs/research/ci-baseline.json."""
    all_baselines = json.loads(BASELINE_PATH.read_text()) if BASELINE_PATH.exists() else {}
    baseline = all_baselines.get(BASELINE_KEY)
    failures = []

    if baseline is None:
        print(f"no baseline recorded yet for {BASELINE_KEY}; recording this run as the new baseline")
    else:
        for cat in ("accessibility", "best_practices", "seo"):
            key = cat.replace("_", "-")
            if scores[key] < baseline[cat]:
                failures.append(f"{cat} dropped from {baseline[cat]} to {scores[key]}")
        perf_floor = baseline["performance"] - PERFORMANCE_NOISE_TOLERANCE
        if scores["performance"] < perf_floor:
            failures.append(
                f"performance dropped from {baseline['performance']} to {scores['performance']}, "
                f"more than the {PERFORMANCE_NOISE_TOLERANCE}-point documented CI-noise band"
            )

    if cls is not None and cls > CLS_GOOD_THRESHOLD:
        failures.append(f"cumulative layout shift {cls} is above Lighthouse's own 'good' line of {CLS_GOOD_THRESHOLD}")

    if failures:
        return failures

    new_entry = {
        "performance": max(scores["performance"], baseline["performance"]) if baseline else scores["performance"],
        "accessibility": max(scores["accessibility"], baseline["accessibility"]) if baseline else scores["accessibility"],
        "best_practices": max(scores["best-practices"], baseline["best_practices"]) if baseline else scores["best-practices"],
        "seo": max(scores["seo"], baseline["seo"]) if baseline else scores["seo"],
    }
    if baseline != new_entry:
        all_baselines[BASELINE_KEY] = new_entry
        BASELINE_PATH.write_text(json.dumps(all_baselines, indent=2, sort_keys=True) + "\n")
        print(f"raised baseline for {BASELINE_KEY}: {new_entry}")
    return []


def main() -> int:
    try:
        _chromium_path()
    except Exception as exc:  # noqa: BLE001 - report and exit cleanly either way
        print(f"no usable Chromium in this environment: {exc}", file=sys.stderr)
        return 1

    static_server, static_port = _start_static_server()
    try:
        landing_url = f"http://127.0.0.1:{static_port}/landing.html"
        report = _run_lighthouse(landing_url)
    finally:
        static_server.shutdown()

    scores = {cat: round(data["score"] * 100) for cat, data in report["categories"].items()}
    cls = report["audits"].get("cumulative-layout-shift", {}).get("numericValue")
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
    if cls is not None:
        print(f"  {'cls':<16} {cls}")
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

    failures = _check_baseline(scores, cls)
    if failures:
        print("\nFAILED baseline check (docs/research/ci-baseline.json):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

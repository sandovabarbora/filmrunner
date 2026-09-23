"""Lighthouse mobile performance score for the public sheet at pilot scale (FR-71).

FR-52's own dod asked for a Lighthouse mobile score for the public sheet; it was
never run (`docs/research/pilot-scale-2026-09.md` recorded "no Lighthouse in the
harness"). `npx lighthouse --version` works in this environment against the
public npm registry, so the harness gap no longer holds — this closes it with the
same FR-52 production (60 crew, 8 cast, 6 locations, 30 days, day 5 has 60 scenes)
and writes the score into that same research file.

Usage: run `npm run build` in frontend/ first, then, with a local Postgres
reachable at FILMRUNNER_DATABASE_URL (defaults to the same test DB the
Playwright E2E suite uses):

    python3 scripts/lighthouse_pilot_scale.py

Prints the performance score and any audit Lighthouse itself flags red
(score < 0.5) or orange (< 0.9), and writes `docs/research/lighthouse-pilot-scale.json`
(the full report) plus a summary appended to
`docs/research/pilot-scale-2026-09.md`. Chrome is the sandbox's own pre-installed
Chromium (CHROME_PATH), never a fresh download — the same pattern the E2E suite
uses for its own browser fixture.
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

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT.parent / "backend"
DIST_DIR = ROOT / "dist"
RESEARCH_DIR = ROOT.parent / "docs" / "research"
REPORT_PATH = RESEARCH_DIR / "lighthouse-pilot-scale.json"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

TOKEN = "lighthouse-pilot-scale"
NAME = "Scale test (FR-52) v2"
DEPARTMENTS = ["AD", "Camera", "Electric", "Grip", "Sound", "Art", "Costume", "Make-up", "Production", "Locations", "Transport", "Catering"]
POSITIONS = ["Head", "1st", "2nd", "Assistant", "Trainee"]
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
    subprocess.run(
        [python, "-c", "from app.database import Base, engine; import app.models; Base.metadata.create_all(engine)"],
        cwd=BACKEND_DIR, env=env, check=True,
    )
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


def _seed(api_url: str) -> str:
    """The same FR-52 production (idempotent by name), reused here rather than
    imported from test_scale.py to keep this script independent of pytest."""
    existing = [p for p in _api(api_url, "GET", "/api/v1/productions") if p["name"] == NAME]
    if existing:
        pid = existing[0]["id"]
        days = _api(api_url, "GET", f"/api/v1/productions/{pid}/call-sheets")
        return next(d["id"] for d in days if d["day_number"] == 5)

    pid = _api(api_url, "POST", "/api/v1/productions", {"name": NAME, "status": "shooting"})["id"]
    crew = []
    for i in range(60):
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        cid = _api(api_url, "POST", "/api/v1/contacts", {"name": f"{dept} Person {i + 1}", "phone": f"+420 7{i:02d} 000 {i:03d}"})["id"]
        crew.append(_api(api_url, "POST", f"/api/v1/productions/{pid}/crew-members", {
            "contact_id": cid, "department": dept, "position": POSITIONS[(i // len(DEPARTMENTS)) % len(POSITIONS)],
            "is_head_of_department": i < len(DEPARTMENTS), "standard_call_time": None}))
    cast = []
    for i in range(8):
        cid = _api(api_url, "POST", "/api/v1/contacts", {"name": f"Actor {i + 1}"})["id"]
        cast.append(_api(api_url, "POST", f"/api/v1/productions/{pid}/cast-members", {"contact_id": cid, "character_name": f"ROLE {i + 1}", "standard_pickup_time": "05:30"}))
    locations = [_api(api_url, "POST", f"/api/v1/productions/{pid}/locations", {
        "name": f"Location {i + 1}", "address": f"Street {i + 1}, Praha", "parking_notes": "Yard, 10 cars", "nearest_hospital": "Bulovka",
        "geo_lat": 50.08 + i * 0.01, "geo_lng": 14.42 + i * 0.01}) for i in range(6)]
    biggest_id = None
    for d in range(30):
        n_scenes = 40 + (d * 5) % 21  # 40-60, day 5 has 60 (same formula as test_scale.py)
        scenes = [{"order_index": s + 1, "scene_number": f"{d * 60 + s + 1}", "int_ext": "EXT" if s % 3 else "INT", "day_night": "NIGHT" if s % 5 == 0 else "DAY",
                   "set_description": f"SET {s + 1} — a description long enough to wrap on a phone, like a real slugline would",
                   "page_count_eighths": 3 + s % 9, "location_id": locations[s % 6]["id"]} for s in range(n_scenes)]
        day = _api(api_url, "POST", f"/api/v1/productions/{pid}/call-sheets", {
            "shoot_date": f"2099-03-{(d % 28) + 1:02d}" if d < 28 else f"2099-04-{d - 27:02d}", "day_number": d + 1, "day_count": 30,
            "initial_revision": {
                "general_crew_call": "06:30", "shooting_call": "07:30", "safety_notes": "Stairs, water, animals on set" if d % 2 else None,
                "head_of_day_crew_member_id": crew[0]["id"], "schedule_items": scenes,
                "cast_calls": [{"cast_member_id": c["id"], "status_code": "W", "pickup_time": "05:30", "call_time": "06:00", "makeup_hair_time": "06:15", "on_set_time": "07:30"} for c in cast[:5]],
                "crew_calls": [{"crew_member_id": crew[k]["id"], "call_time": "05:15", "note": "early"} for k in range(1, 6)],
            }})
        if day["day_number"] == 5:
            biggest_id = day["id"]
    return biggest_id


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
    frontend_url = f"http://127.0.0.1:{static_port}"
    api_proc, api_url = _start_api()
    try:
        big_id = _seed(api_url)
        sheet_url = f"{frontend_url}/?sheet={big_id}&api={api_url}"
        report = _run_lighthouse(sheet_url)
    finally:
        static_server.shutdown()
        api_proc.terminate()
        api_proc.wait(timeout=10)

    scores = {cat: round(data["score"] * 100) for cat, data in report["categories"].items()}
    red_audits = [
        (aid, a["title"], a["score"]) for aid, a in report["audits"].items()
        if a.get("score") is not None and a["scoreDisplayMode"] == "numeric" and a["score"] < 0.5
    ]

    print("--- Lighthouse, mobile, public sheet, FR-52 pilot-scale production (60 scenes) ---")
    for cat, score in scores.items():
        print(f"  {cat:<16} {score}")
    if red_audits:
        print("  red audits (score < 0.5):")
        for aid, title, score in red_audits:
            print(f"    {aid:<40} {title:<50} {round(score * 100)}")
    else:
        print("  no red audits")

    print(f"\nwrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

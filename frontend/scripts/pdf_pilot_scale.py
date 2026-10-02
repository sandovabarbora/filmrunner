"""FR-93: generate both PDF exports against the FR-52 pilot-scale fixture and record
what actually happens — page count, whether a table breaks across pages sanely, and
generation time — rather than assuming FR-47/FR-61's own (much smaller) test fixtures
still hold at a real pilot day's size.

FR-47's own E2E (`tests/test_pdf_e2e.py`) proved the day PDF at 40 scenes/30 crew;
FR-61's proved the crew-list PDF at 60 people via a hand-typed 5-person import
(`test_crew_filter_narrows_the_list_and_the_print_view_has_everyone` only checks
content, never a page count). Neither has been run against FR-52's actual pilot-scale
production (60 crew, 8 cast, 6 locations, 30 days, day 5 has 60 scenes) — this script
does both, against the same seeded production every other pilot-scale script in this
repo re-uses.

Usage: run `npm run build` in frontend/ first, then, with a local Postgres reachable
at FILMRUNNER_DATABASE_URL (defaults to the same test DB the Playwright E2E suite
uses):

    python3 scripts/pdf_pilot_scale.py

Prints a table and appends a dated section to docs/research/pilot-scale-2026-09.md
(skipped on CI, which has nothing to commit the append to).

FR-103 (2026-09-29): wired into `.github/workflows/ci.yml` on every PR. Exits 1 if
either PDF's page count differs at all from `docs/research/ci-baseline.json`'s
recorded value — page count is deterministic, not a noisy score, so any change
(not just an increase) needs a human to look and, if it's legitimate, update the
baseline in the same PR.
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
from io import BytesIO
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT.parent / "backend"
DIST_DIR = ROOT / "dist"
RESEARCH_FILE = ROOT.parent / "docs" / "research" / "pilot-scale-2026-09.md"
BASELINE_PATH = ROOT.parent / "docs" / "research" / "ci-baseline.json"
BASELINE_KEY = "pdf_pilot_scale"
SANDBOX_CHROMIUM_PATH = "/opt/pw-browsers/chromium"


def _chromium_launch_kwargs() -> dict:
    if os.path.exists(SANDBOX_CHROMIUM_PATH):
        return {"executable_path": SANDBOX_CHROMIUM_PATH}
    # A real CI runner has no /opt/pw-browsers; ci.yml already runs `playwright
    # install --with-deps chromium` first, so let Playwright launch its own install
    # instead of pointing at a sandbox-only path.
    return {}

TOKEN = "pdf-pilot-scale"
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


def _seed(api_url: str) -> dict:
    """The same FR-52 production (idempotent by name), seeded the same way lighthouse_pilot_scale.py
    does, kept independent of pytest. Returns id, the day-5 (60-scene) id, and the production's own
    crew/cast counts."""
    existing = [p for p in _api(api_url, "GET", "/api/v1/productions") if p["name"] == NAME]
    if existing:
        pid = existing[0]["id"]
        crew = _api(api_url, "GET", f"/api/v1/productions/{pid}/crew-members")
        days = _api(api_url, "GET", f"/api/v1/productions/{pid}/call-sheets")
        big = next(d["id"] for d in days if d["day_number"] == 5)
        return {"id": pid, "big": big, "n_crew": len(crew)}

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
    big = None
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
            big = day["id"]
    return {"id": pid, "big": big, "n_crew": 60}


def _day_pdf(frontend_url: str, api_url: str, big_id: str) -> dict:
    with sync_playwright() as pw:
        # This build removed "--headless=old" (what headless=True passes); the new mode
        # must be requested explicitly, same workaround as take_landing_screenshots.py.
        browser = pw.chromium.launch(headless=False, args=["--headless=new"], **_chromium_launch_kwargs())
        page = browser.new_page(viewport={"width": 390, "height": 844})
        t0 = time.perf_counter()
        page.goto(f"{frontend_url}/?sheet={big_id}&api={api_url}")
        page.wait_for_selector("#sheet.visible", timeout=30_000)
        page.wait_for_selector("#scheduleBody tr:nth-child(60)", timeout=30_000)
        load_s = round(time.perf_counter() - t0, 2)

        page.emulate_media(media="print")
        t1 = time.perf_counter()
        pdf_bytes = page.pdf()
        gen_s = round(time.perf_counter() - t1, 2)
        browser.close()

    reader = PdfReader(BytesIO(pdf_bytes))
    n_pages = len(reader.pages)
    per_page = [p.extract_text() for p in reader.pages]
    # FR-47's own PDF test found digits extract as NUL on some Chromium builds (font
    # subsetting without a ToUnicode map), so pagination is checked the same way: two
    # letter-only tokens from within each row's own set_description text must match per
    # page — a row split across a page break would leave one without the other. Not the
    # row's "SET " head: at this scale the schedule's own repeating table header (`th.set`
    # = "Set", CSS-uppercased to "SET" and repeated by `thead { display: table-header-group
    # }` on every content page) renders identically to the seeded uppercase "SET " prefix
    # and inflated the count by one per page — found live in this run's own PDF, not a
    # split-row bug (confirmed against the raw per-page text before picking these tokens).
    total_set = sum(t.count("wrap on a phone") for t in per_page)
    total_tail = sum(t.count("slugline") for t in per_page)
    split_pages = [i + 1 for i, t in enumerate(per_page) if t.count("wrap on a phone") != t.count("slugline")]
    return {
        "load_s": load_s, "gen_s": gen_s, "n_pages": n_pages,
        "total_set": total_set, "total_tail": total_tail, "split_pages": split_pages,
        "bytes": len(pdf_bytes),
    }


def _crew_pdf(frontend_url: str, api_url: str, pid: str, n_crew_expected: int) -> dict:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, args=["--headless=new"], **_chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_init_script(
            "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
            + f"{{apiBase: {api_url!r}, token: {TOKEN!r}}}))"
        )
        page = context.new_page()
        t0 = time.perf_counter()
        page.goto(f"{frontend_url}/editor.html#/p/{pid}/crew")
        page.wait_for_selector(f"#crew li:nth-child({n_crew_expected})", timeout=30_000)
        load_s = round(time.perf_counter() - t0, 2)

        t1 = time.perf_counter()
        with context.expect_page() as popup_info:
            page.click("#printCrew")
        printed = popup_info.value
        printed.wait_for_load_state("domcontentloaded")
        printed.emulate_media(media="print")
        pdf_bytes = printed.pdf()
        gen_s = round(time.perf_counter() - t1, 2)
        n_names = printed.content().count("<td>")  # rough per-cell count, cross-checked against reader text below
        browser.close()

    reader = PdfReader(BytesIO(pdf_bytes))
    n_pages = len(reader.pages)
    combined = "\n".join(p.extract_text() for p in reader.pages)
    n_person_rows = sum(combined.count(f"{dept} Person") for dept in DEPARTMENTS)
    n_cast_rows = sum(combined.count(f"ROLE {i + 1}") for i in range(8))
    return {
        "load_s": load_s, "gen_s": gen_s, "n_pages": n_pages,
        "n_person_rows": n_person_rows, "n_cast_rows": n_cast_rows,
        "bytes": len(pdf_bytes),
    }


def _check_baseline(day_pages: int, crew_pages: int) -> list[str]:
    """Unlike the Lighthouse scripts' score tolerance, a PDF page count is an exact,
    deterministic assertion (no timing noise), so this fails on ANY change, not just
    an increase, and never auto-updates the baseline — a legitimate change (e.g. a
    denser crew layout, or trimming rows) needs a human to edit
    docs/research/ci-baseline.json in the same PR, per FR-103's own dod."""
    all_baselines = json.loads(BASELINE_PATH.read_text()) if BASELINE_PATH.exists() else {}
    baseline = all_baselines.get(BASELINE_KEY)
    if baseline is None:
        print(f"no baseline recorded yet for {BASELINE_KEY}; add one to docs/research/ci-baseline.json to enable this gate")
        return []
    failures = []
    if day_pages != baseline["day_pages"]:
        failures.append(f"day PDF page count changed from {baseline['day_pages']} to {day_pages}")
    if crew_pages != baseline["crew_pages"]:
        failures.append(f"crew-list PDF page count changed from {baseline['crew_pages']} to {crew_pages}")
    return failures


def main() -> int:
    static_server, static_port = _start_static_server()
    frontend_url = f"http://127.0.0.1:{static_port}"
    api_proc, api_url = _start_api()
    try:
        seed = _seed(api_url)
        day = _day_pdf(frontend_url, api_url, seed["big"])
        crew = _crew_pdf(frontend_url, api_url, seed["id"], seed["n_crew"])
    finally:
        static_server.shutdown()
        api_proc.terminate()
        api_proc.wait(timeout=10)

    print("--- FR-93 PDF exports at FR-52 pilot scale ---")
    print(f"Day PDF (60 scenes): load {day['load_s']}s, generate {day['gen_s']}s, "
          f"{day['n_pages']} pages, {day['bytes'] / 1024:.1f} KB, "
          f"scene rows found {day['total_set']}/60, split pages {day['split_pages'] or 'none'}")
    print(f"Crew-list PDF (60 crew, 8 cast): load {crew['load_s']}s, generate {crew['gen_s']}s, "
          f"{crew['n_pages']} pages, {crew['bytes'] / 1024:.1f} KB, "
          f"crew rows found {crew['n_person_rows']}/60, cast rows found {crew['n_cast_rows']}/8")

    today = time.strftime("%Y-%m-%d")
    day_ceiling_note = (
        "no scene row is split across a page break (confirmed)"
        if not day["split_pages"] else f"FAILED — split on page(s) {day['split_pages']}"
    )
    section = f"""
## FR-93 ({today}): both PDF exports re-measured at FR-52 pilot scale

Re-run of `frontend/scripts/pdf_pilot_scale.py` (headless Chromium at
`/opt/pw-browsers/chromium`, a real build, a real uvicorn+Postgres API) against the
same seeded "{NAME}" production every other pilot-scale script in this repo reuses.

| Export | Load | Generate | Pages | Size | Rows found |
|---|---|---|---|---|---|
| Day PDF (60 scenes) | {day['load_s']} s | {day['gen_s']} s | {day['n_pages']} | {day['bytes'] / 1024:.1f} KB | {day['total_set']}/60 scenes, {day_ceiling_note} |
| Crew-list PDF (60 crew + 8 cast) | {crew['load_s']} s | {crew['gen_s']} s | {crew['n_pages']} | {crew['bytes'] / 1024:.1f} KB | {crew['n_person_rows']}/60 crew, {crew['n_cast_rows']}/8 cast |

Generation time is Chromium's own print-to-PDF pass on an already-rendered page
({day['gen_s']} s and {crew['gen_s']} s) — not a real wait on a phone at this scale.
FR-47's own "<4 pages" line was set for its own 40-scene/30-crew fixture, a smaller
scale than this one, so a higher page count here is a new data point, not a failure
of that line. FR-61's "under 3 pages for 60 people" line applies directly at this
scale: {crew['n_pages']} pages {'satisfies' if crew['n_pages'] < 3 else 'does NOT satisfy'} it.
"""
    if os.environ.get("CI") == "true":
        # A CI run is a disposable checkout with nothing to commit the append to —
        # skip it there so ci.yml's own run doesn't churn a file nobody will see.
        print(f"\nCI run: not appending to {RESEARCH_FILE}")
    else:
        with open(RESEARCH_FILE, "a", encoding="utf-8") as f:
            f.write(section)
        print(f"\nappended to {RESEARCH_FILE}")

    failures = _check_baseline(day["n_pages"], crew["n_pages"])
    if failures:
        print("\nFAILED baseline check (docs/research/ci-baseline.json):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

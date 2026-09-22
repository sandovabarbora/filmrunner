"""Record the 30-second landing-page flow video (FR-54): create a day, publish,
open the crew link, publish a hot revision, and show "REV B replaces A" — the
same flow a Prague AD would run on their own phone.

Usage: run `npm run build` in frontend/ first, then, with a local Postgres
reachable at FILMRUNNER_DATABASE_URL (defaults to the same test DB the
Playwright E2E suite uses):

    python3 scripts/record_landing_flow.py

Writes `public/landing/landing-flow.webm`. Unlike take_landing_screenshots.py,
this script does NOT skip a failed step: a missing selector means the flow
itself no longer works as advertised, so it raises and exits non-zero rather
than shipping a stale or partial recording. Re-run after any change to the
editor's create/publish/crew-link flow to refresh it.
"""

import http.server
import os
import shutil
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
OUT_DIR = ROOT / "public" / "landing"
OUT_FILE = OUT_DIR / "landing-flow.webm"
CHROMIUM_PATH = "/opt/pw-browsers/chromium"
FFMPEG_PATH = "/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux"
MAX_BYTES = 3 * 1024 * 1024

TOKEN = "landing-flow-recorder"
VIEWPORT = {"width": 390, "height": 844}
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
        # A recording session drives every step in well under a minute; the
        # public-endpoint abuse guard (FR-51) is not what this script tests.
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


def _shrink_to_limit(path: Path, max_bytes: int) -> None:
    """The raw VP8 capture is already small at this viewport and length, but
    re-encode at a lower bitrate if a slower flow ever pushes it over the cap
    — never ship an oversized file silently."""
    if path.stat().st_size <= max_bytes or not os.path.exists(FFMPEG_PATH):
        return
    tmp = path.with_suffix(".compressed.webm")
    subprocess.run(
        [FFMPEG_PATH, "-y", "-i", str(path), "-c:v", "libvpx", "-b:v", "300k", "-an", str(tmp)],
        check=True, capture_output=True,
    )
    if tmp.stat().st_size < path.stat().st_size:
        tmp.replace(path)
    else:
        tmp.unlink(missing_ok=True)


def _connect(page, api_url: str) -> None:
    page.add_init_script(
        "localStorage.setItem('filmrunner.editor.connection', JSON.stringify("
        + f"{{apiBase: {api_url!r}, token: {TOKEN!r}}}))"
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    static_server, static_port = _start_static_server()
    frontend_url = f"http://127.0.0.1:{static_port}"
    api_proc, api_url = _start_api()

    video_dir = OUT_DIR / "_recording_tmp"
    if video_dir.exists():
        shutil.rmtree(video_dir)
    video_dir.mkdir()

    try:
        with sync_playwright() as pw:
            if os.path.exists(CHROMIUM_PATH):
                browser = pw.chromium.launch(executable_path=CHROMIUM_PATH, headless=False, args=["--headless=new"])
            else:
                browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=VIEWPORT,
                record_video_dir=str(video_dir),
                record_video_size=VIEWPORT,
            )
            page = context.new_page()
            _connect(page, api_url)

            page.goto(f"{frontend_url}/editor.html")
            page.wait_for_selector("#newProduction", timeout=15_000)
            page.wait_for_timeout(500)
            page.fill("#newProduction", "Noc na Vltavě")
            page.click("#createProduction")
            page.wait_for_selector("#newDay", timeout=15_000)
            page.wait_for_timeout(700)

            page.click("role=tab[name='Crew']")
            page.wait_for_selector("#crewName", timeout=15_000)
            page.fill("#crewName", "Eva Dvořáková")
            page.fill("#crewPhone", "+420 777 111 222")
            page.fill("#crewDept", "AD")
            page.fill("#crewPos", "1st AD")
            page.check("#crewHod")
            page.click("#addCrew")
            page.wait_for_selector("#crew", timeout=15_000)
            page.wait_for_timeout(1600)

            page.click("role=tab[name='Days']")
            page.click("#newDay")
            page.wait_for_selector("#general_crew_call", timeout=15_000)
            page.fill("#general_crew_call", "06:30")
            page.click("#addScene")
            page.locator("#items .item").nth(0).get_by_label("Scene").fill("42")
            page.locator("#items .item").nth(0).get_by_label("Set").fill("NÁBŘEŽÍ, TROJA")
            page.select_option("#headOfDay", label="Eva Dvořáková · 1st AD (HoD)")
            page.wait_for_timeout(1000)
            page.click("#publish")
            page.wait_for_selector("#notice", timeout=20_000)
            page.wait_for_function(
                "document.querySelector('#notice')?.textContent?.includes('Published REV A')", timeout=20_000
            )
            day_url = page.url
            share_link = page.locator("#shareLink").get_attribute("href", timeout=15_000)
            if not share_link:
                raise RuntimeError("no #shareLink after publishing REV A — the recorded flow is broken")
            page.wait_for_timeout(1400)

            page.goto(share_link)
            page.wait_for_selector("#sheet.visible", timeout=20_000)
            page.wait_for_timeout(3200)

            page.goto(day_url)
            page.wait_for_selector("#general_crew_call", timeout=15_000)
            page.fill("#general_crew_call", "07:30")
            page.wait_for_timeout(900)
            page.click("#publish")
            page.wait_for_function(
                "document.querySelector('#notice')?.textContent?.includes('Published REV B')", timeout=20_000
            )
            page.wait_for_timeout(1400)

            page.goto(share_link)
            page.wait_for_selector("#revReplaces", timeout=20_000)
            page.wait_for_timeout(2200)

            video_path = page.video.path()
            context.close()
            browser.close()
    finally:
        static_server.shutdown()
        api_proc.terminate()
        api_proc.wait(timeout=10)

    recorded = Path(video_path)
    if not recorded.exists():
        raise RuntimeError("Playwright produced no video file")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(recorded), str(OUT_FILE))
    shutil.rmtree(video_dir, ignore_errors=True)

    _shrink_to_limit(OUT_FILE, MAX_BYTES)
    size_kb = OUT_FILE.stat().st_size / 1024
    if OUT_FILE.stat().st_size > MAX_BYTES:
        print(f"warning: {OUT_FILE} is {size_kb:.0f} KB, over the 3 MB cap", file=sys.stderr)
        return 1
    print(f"wrote {OUT_FILE} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared fixtures: the built frontend served over a local static server,
and a real backend (uvicorn on the test database) both E2E test files use."""

import http.server
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest
from playwright.sync_api import BrowserType

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
TEST_DB_URL = os.environ.get(
    "FILMRUNNER_DATABASE_URL",
    "postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner_test",
)
E2E_TOKEN = "e2e-token"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # noqa: D102
        pass


def find_fallback_chromium(pinned_executable: Path) -> Path | None:
    """Look for any other installed Chromium build next to a missing pinned one.

    `pinned_executable` is playwright's own resolved path, e.g.
    `<browsers_root>/chromium-1134/chrome-linux/chrome`. Only used once that
    exact path is confirmed absent (FR-107) — a runner that has the pinned
    revision must never be redirected elsewhere.
    """
    browsers_root = pinned_executable.parents[2]
    if not browsers_root.is_dir():
        return None
    for candidate in sorted(browsers_root.glob("chromium-*/chrome-linux/chrome"), reverse=True):
        if candidate.is_file():
            return candidate
    alias = browsers_root / "chromium"  # some environments ship a plain convenience symlink
    if alias.exists():
        return alias
    return None


def resolve_chromium_launch_args(base_args: dict, pinned_executable: Path) -> dict:
    """Add a fallback `executable_path` to `base_args` when `pinned_executable` is missing.

    Raises `RuntimeError` naming the missing browser when no fallback exists either
    (FR-107's own failure case), instead of leaving Playwright to fail the launch with
    a generic timeout.
    """
    if pinned_executable.exists():
        return base_args
    fallback = find_fallback_chromium(pinned_executable)
    if fallback is None:
        raise RuntimeError(
            f"No Chromium build found for the E2E suite: the pinned revision is missing "
            f"at {pinned_executable}, and no fallback build exists under "
            f"{pinned_executable.parents[2]}. Run `playwright install chromium`, or set "
            "PLAYWRIGHT_BROWSERS_PATH to a directory that has one."
        )
    args = {**base_args, "executable_path": str(fallback)}
    if args.get("headless", True):
        # A fallback build newer than the pinned revision may have dropped "old" headless
        # mode (this playwright version still launches with --headless=old by default);
        # "new" headless works on every Chromium this fallback could plausibly find.
        args["args"] = [*args.get("args", []), "--headless=new"]
    return args


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict, browser_type: BrowserType) -> dict:
    """Fall back to any installed Chromium when the pinned revision is missing.

    `playwright==1.47.0` (pinned in requirements.txt) expects chromium-1134;
    this sandbox pre-installs a newer revision instead, so every prior shift
    hand-patched this exact fixture and reverted it before committing rather
    than fix it once (FR-107). A CI runner with the pinned revision installed
    is unaffected: the fallback only triggers once that revision is confirmed
    absent, never preferred over it.
    """
    if browser_type.name != "chromium":
        return browser_type_launch_args
    return resolve_chromium_launch_args(browser_type_launch_args, Path(browser_type.executable_path))


@pytest.fixture(scope="session")
def frontend_url() -> Iterator[str]:
    assert (DIST_DIR / "index.html").exists(), "run `npm run build` in frontend/ first"
    handler = partial(_QuietHandler, directory=str(DIST_DIR))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def api_url() -> Iterator[str]:
    env = {
        **os.environ,
        "FILMRUNNER_DATABASE_URL": TEST_DB_URL,
        "FILMRUNNER_API_BEARER_TOKEN": E2E_TOKEN,
        "FILMRUNNER_ENVIRONMENT": "development",
        "FILMRUNNER_CORS_ORIGINS": "*",
        # FR-51: the whole E2E suite hits the public routes from one IP within a minute; the guard is not under test here.
        "FILMRUNNER_PUBLIC_RATE_LIMIT_PER_IP": "0",
        "FILMRUNNER_PUBLIC_RATE_LIMIT_PER_TOKEN": "0",
    }
    subprocess.run(
        [sys.executable, "-c", "from app.database import Base, engine; import app.models; Base.metadata.create_all(engine)"],
        cwd=BACKEND_DIR, env=env, check=True,
    )
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
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
    yield url
    proc.terminate()
    proc.wait(timeout=10)

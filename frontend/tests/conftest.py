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

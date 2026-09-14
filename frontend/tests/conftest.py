"""Shared fixtures: the built frontend served over a local static server."""

import http.server
import socketserver
import threading
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest

DIST_DIR = Path(__file__).resolve().parents[1] / "dist"


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

"""One line per request, safe to keep: personal tokens are credentials and live in URL paths, so the path is never logged."""

import logging
import re
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("filmrunner.request")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _route_template(scope: Scope) -> str:
    # FastAPI's route.path leaves out the include_router prefix; every API route shares /api/v1, so it stays unambiguous.
    route = scope.get("route")
    return getattr(route, "path", None) or "(unmatched)"


def _request_id(scope: Scope) -> str:
    # Anyone can send this header, so only a plain id may reach a log line.
    raw = dict(scope["headers"]).get(b"fly-request-id", b"").decode("latin-1")
    return raw if _REQUEST_ID.match(raw) else "-"


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500
        logged = False

        def log() -> None:
            nonlocal logged
            logged = True
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info("%s %s %d %.0fms request_id=%s", scope["method"], _route_template(scope), status, elapsed_ms, _request_id(scope))

        async def recording_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)
            # Logged at the last byte: background tasks (push fan-out) run after it and are not request time.
            if message["type"] == "http.response.body" and not message.get("more_body") and not logged:
                log()

        try:
            await self.app(scope, receive, recording_send)
        finally:
            if not logged:
                log()

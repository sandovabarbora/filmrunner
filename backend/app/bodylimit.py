"""FR-220: a cap on request bodies, in front of everything that reads them.

FastAPI reads and parses a body before it resolves dependencies, so auth runs
too late to protect a 256 MB machine: an anonymous POST of any size would be
buffered first and refused afterwards. The declared Content-Length is refused
up front, and the bytes are counted as they arrive, because the header can be
missing (chunked) or wrong.

Sits inside CORSMiddleware so the browser can read the 413, same as the 429.
"""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_LIMIT = 256 * 1024
# Above the handlers' own limits (10 MB PDF, 300 KB photo) plus multipart framing, so a slightly
# oversized file reaches the handler and gets its specific message rather than this generic one.
UPLOAD_LIMIT = 12 * 1024 * 1024
UPLOAD_ROUTES = (
    re.compile(r"^/api/v1/productions/[^/]+/import/call-sheet-pdf$"),
    re.compile(r"^/api/v1/contacts/[^/]+/photo$"),
)


def _limit_for(method: str, path: str) -> int:
    if method == "POST" and any(route.match(path) for route in UPLOAD_ROUTES):
        return UPLOAD_LIMIT
    return DEFAULT_LIMIT


def _declared_length(scope: Scope) -> int | None:
    """None when absent or unparseable: the running count below still applies."""
    for name, value in scope["headers"]:
        if name == b"content-length":
            return int(value) if value.isdigit() else None
    return None


def _detail(limit: int) -> str:
    return f"This request is too large; the limit here is {limit // 1024} KB"


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = _limit_for(scope["method"], scope["path"])
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            # The rest of the body is never read, so the connection cannot be reused for another request.
            response = JSONResponse({"detail": _detail(limit)}, status_code=status.HTTP_413_CONTENT_TOO_LARGE, headers={"Connection": "close"})
            await response(scope, receive, send)
            return

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI's body parsing turns every other exception type into a 400.
                    raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=_detail(limit), headers={"Connection": "close"})
            return message

        await self.app(scope, counting_receive, send)

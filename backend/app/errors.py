"""The last line of defence for an unhandled exception.

FastAPI's `exception_handler(Exception)` cannot do this job: Starlette runs that
handler in ServerErrorMiddleware, outside every other middleware, so its response
never passes through CORS and the browser hides it from the page. This sits inside
CORSMiddleware instead.
"""

import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class UnhandledErrorMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            # The route's template, not the URL: a URL can hold someone's personal link token.
            route = getattr(scope.get("route"), "path", "no matching route")
            logger.exception("Unhandled error on %s %s", scope["method"], route)
            # Once the response has started (a background task after the reply) a second one cannot be sent.
            if not response_started:
                await JSONResponse({"detail": "Internal server error"}, status_code=500)(scope, receive, send)

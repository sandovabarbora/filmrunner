"""FR-51: an abuse guard on the unauthenticated routes (ADR-008).

The public router is open by design — FR-13 personal tokens are the
credential — so the only thing standing between the internet and a loop that
probes tokens or fills `revision_views` is this: a sliding one-minute window
per client IP on everything under /api/v1/public/, and a tighter one per
personal token on the routes that carry one. In-process (one Fly machine); a
second machine would need a shared store, which ADR-008 says when to do.

Sized for the 05:00 rush: a whole crew opening the sheet from one production
office Wi-Fi is one IP making ~5 requests per person (sheet, personal block,
seen, next, vapid key) — 40 people × 5 = 200 in a minute, under the 300
default with room to reload. The per-token limit only ever hits one person.

FR-128: that count leaves out crew photos. `GET /public/contacts/{id}/photo`
(FR-18) is an `<img src>` on every contact row the sheet renders — the
sheet's own department plus "others" — so one device load can fetch a photo
per other crew member, not per person; 40 crew all with a photo can mean up
to ~40 photo requests per device, ~1,600 from one IP, which would blow past
even a generous functional budget and 429 the next functional call behind
it. The photo route is unauthenticated but not a probing or write-abuse
vector (ADR-008's threat model) and is `Cache-Control: max-age=86400`, so it
gets its own, more generous per-IP window instead of sharing the functional
one — a photo burst can no longer starve the next real `/seen` or `/me` call
on the same Wi-Fi.
"""

from __future__ import annotations

import re
import time
from collections import deque
from threading import Lock

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

PUBLIC_PREFIX = "/api/v1/public/"
TOKEN_ROUTES = [
    re.compile(r"^/api/v1/public/crew/([^/]+)/"),
    re.compile(r"^/api/v1/public/call-sheets/[^/]+/(?:me|seen|confirm)/([^/]+)$"),
]
PHOTO_ROUTE = re.compile(r"^/api/v1/public/contacts/[^/]+/photo$")
WINDOW_SECONDS = 60


class SlidingWindow:
    """Timestamps per key; `hit` records one request and says whether the key is over its limit."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= WINDOW_SECONDS:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(1, int(WINDOW_SECONDS - (now - q[0])) + 1)
            q.append(now)
            # Keep the table from growing with every IP that ever visited.
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= WINDOW_SECONDS][:1000]:
                    self._hits.pop(k, None)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    """Fly puts the real client in Fly-Client-IP; behind other proxies X-Forwarded-For's first hop; else the socket."""
    fly = request.headers.get("fly-client-ip")
    if fly:
        return fly.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def token_of(path: str) -> str | None:
    for pattern in TOKEN_ROUTES:
        m = pattern.match(path)
        if m:
            return m.group(1)
    return None


INSTANCES: list["RateLimitMiddleware"] = []  # so tests (and an admin reset, if ever) can clear the windows


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, per_ip: int, per_token: int, per_ip_photos: int = 0) -> None:
        self.app = app
        self.per_ip = SlidingWindow(per_ip) if per_ip > 0 else None
        self.per_token = SlidingWindow(per_token) if per_token > 0 else None
        self.per_ip_photos = SlidingWindow(per_ip_photos) if per_ip_photos > 0 else None
        INSTANCES.append(self)

    def reset(self) -> None:
        for w in (self.per_ip, self.per_token, self.per_ip_photos):
            if w:
                w.reset()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(PUBLIC_PREFIX) or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        checks: list[tuple[SlidingWindow, str]] = []
        # FR-128: a photo load has its own budget and never counts against the functional one,
        # so a burst of avatar fetches can't 429 the next real /seen or /me call on the same Wi-Fi.
        if self.per_ip_photos and PHOTO_ROUTE.match(scope["path"]):
            checks.append((self.per_ip_photos, f"photo-ip:{client_ip(request)}"))
        else:
            if self.per_ip:
                checks.append((self.per_ip, f"ip:{client_ip(request)}"))
            token = token_of(scope["path"])
            if token and self.per_token:
                checks.append((self.per_token, f"token:{token}"))
        for window, key in checks:
            allowed, retry_after = window.hit(key)
            if not allowed:
                response = JSONResponse(
                    {"detail": "Too many requests from this client; try again in a moment"},
                    status_code=429, headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

# ADR-008 · Rate limit on the public endpoints

Date: 2026-09-22 · Status: accepted · Item: FR-51

## Context

Everything under `/api/v1/public/` is unauthenticated by design: the crew reads the sheet by link, and a personal token (FR-13) is the only credential for the personal block, read receipts (FR-36), the stable link (FR-32) and push subscriptions (FR-16). Before a pilot with a public URL there has to be a ceiling on how fast an unknown client can probe tokens or fill `revision_views` — without touching the one legitimate burst the product exists for: a whole crew opening the sheet at 05:00, often from one production-office Wi-Fi, i.e. one IP.

## Decision

An ASGI middleware (`app/ratelimit.py`) with three sliding one-minute windows, in process:

- **per client IP** on every `/api/v1/public/*` request: **300/min** (`FILMRUNNER_PUBLIC_RATE_LIMIT_PER_IP`);
- **per personal token** on the routes that carry one (`/public/crew/{token}/…`, `/public/call-sheets/{id}/me/{token}`, `…/seen/{token}`): **30/min** (`FILMRUNNER_PUBLIC_RATE_LIMIT_PER_TOKEN`);
- **per client IP, photo route only** (FR-128, 2026-10-05, PR #350): `GET /api/v1/public/contacts/{id}/photo` — **3000/min** (`FILMRUNNER_PUBLIC_RATE_LIMIT_PER_IP_PHOTOS`), its own separate window, never shared with or counted against the functional per-IP/per-token windows above.

Over the limit: `429` with `Retry-After`, CORS headers intact (the guard sits inside the CORS middleware). `OPTIONS`, `/healthz` and every authenticated route are never limited. `0` disables a limit (the E2E harness does that).

The client IP is `Fly-Client-IP` (what Fly's proxy sets), then the first `X-Forwarded-For` hop, then the socket.

### Sizing

One person opening their sheet costs about five public requests (sheet, personal block, seen, next-day, VAPID key). 40 people on one IP inside a minute is 200 — under 300 with room for reloads; a test pins this case. A token limit of 30/min only ever hits one person, and a probing loop cannot use it: distinct bogus tokens each get their own window, so the IP window is what stops a scan (300 distinct tokens per minute per IP at most).

The photo route is a separate case (FR-128): `GET /public/contacts/{id}/photo` is an `<img src>` on every contact row the sheet renders — the sheet's own department plus "others" — so one device load can fetch a photo per other crew member, not per person. 40 crew all with a photo can mean up to ~40 photo requests per device, ~1,600 from one IP, which would blow past even the 300/min functional budget and 429 the next real `/seen` or `/me` call on the same Wi-Fi. The photo route is unauthenticated but is not a probing or write-abuse vector (this ADR's threat model) and is served `Cache-Control: max-age=86400`, so it gets its own, more generous per-IP budget (3000/min) instead of sharing the functional one.

## Consequences

- One Fly machine, one process: the counters live in memory and reset on deploy. Fine at pilot scale. The day `filmrunner-api` runs on two machines, the windows must move to a shared store (Postgres would do; a `rate_limit_hits` table with a periodic delete) — or Fly's own edge limits — and this ADR gets an addendum.
- The counters do not distinguish a NAT with 300 phones behind it from an attacker; a large studio Wi-Fi will be the first to notice. The number is a setting, not a constant.
- Nothing is logged per hit; a 429 is not an incident, just a wall.
- The window counts requests, not bytes. `app/bodylimit.py` (FR-220) caps bodies at 256 KB, 12 MB on the PDF import and photo upload routes, on every route rather than only the public ones, because FastAPI reads a body before auth runs. It sits inside this middleware and inside CORS.

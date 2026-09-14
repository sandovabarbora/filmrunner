# FilmRunner — Call Sheet Skeleton

A narrow, high-polish slice of FilmRunner: creating, revising, and
distributing shoot-day call sheets, viewable offline on set. Not the
full production-management platform (no budgeting, scripts/breakdowns,
scheduling optimizer, SSO, billing) — see `DESIGN.md` for what's in scope
and why, and what's deliberately deferred.

## Stack

- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL, stub bearer-token auth.
- **Frontend**: React + Vite + TypeScript PWA (`frontend/`), IndexedDB cache + Workbox service worker via `vite-plugin-pwa`. See `docs/adr/ADR-001-frontend-stack.md`.
- **Local dev**: docker-compose (Postgres + backend + a static file server for the frontend).

## How this company runs

FilmRunner is run by one founder and an AI team. The operating model,
approval contract, roles and the daily routine are in
`docs/company/TEAM.md`; strategy questions in `docs/company/BRIEF.md`;
work in `docs/company/BACKLOG.md`. Nothing with real-world effect happens
without an approved item in `docs/company/INBOX.md`.

## Live demo

https://sandovabarbora.github.io/filmrunner/ serves the PWA from GitHub
Pages with a bundled sample shoot day (no backend). `?sheet=<id>&api=<base>`
loads a real call sheet from a FilmRunner API; `?dev=1` shows the lookup form. Open it on a
phone, add it to the home screen, switch to airplane mode: the call sheet
still renders from the cache. Deployed by `.github/workflows/pages.yml` on
every push to `main` that touches `frontend/`.

## Production (API)

API on Fly.io (`backend/fly.toml`, region fra), Postgres on Supabase used
as plain Postgres, see `docs/adr/ADR-002-hosting.md`. Deploy is manual
and founder-only: `cd backend && fly deploy` (migrations run as the
release command). Secrets live in Fly only. After the first deploy, seed
one realistic demo production and call sheet so the live URL shows
something real on first open: `cd backend && python -m app.seed_demo`
(idempotent — safe to re-run, it finds the existing demo call sheet by
name instead of duplicating it). It prints the call sheet id to build the
`?sheet=<id>&api=<base>` link from.

## Quick start

```bash
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`, health at `/healthz`)
- Frontend: http://localhost:8080 (Vite dev server). `?dev=1` shows the
  lookup form: API base `http://localhost:8000` and a call sheet ID.
- Default dev bearer token: `dev-only-token-change-me` (set via
  `FILMRUNNER_API_BEARER_TOKEN`; change it before this goes anywhere
  outside your own machine).

Without Docker: create a Postgres DB, copy `backend/.env.example` to
`backend/.env` and adjust `FILMRUNNER_DATABASE_URL`, then:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## What's actually been verified (not just written)

Everything below was run, not assumed, in this session:

- **Schema & migrations**: `alembic revision --autogenerate` correctly
  detected all 10 tables from the models; `alembic upgrade head` applied
  cleanly against a real local Postgres 16 instance; verified with `\dt`.
- **API, end to end over real HTTP**: created a contact, a production, a
  location, a call sheet with an initial revision (schedule item included),
  fetched it both via the authed and public endpoints, published a "hot"
  revision B, and confirmed in the database that revision A's `is_current`
  flag flipped to `false` while B's is `true`. Confirmed a request with no
  bearer token gets a 401.
- **Automated test suite**: 11 pytest tests, run against a real Postgres
  test database (not sqlite, not mocks) inside a rolled-back
  transaction/savepoint per test. Covers auth (missing/wrong/correct token),
  production CRUD + 404s, call sheet creation, the public unauthenticated
  read, revision supersession, and the 26-revision-per-day (A-Z) exhaustion
  guard actually raising instead of silently wrapping around.
- **Frontend, in a real headless browser (Playwright/Chromium)**: loaded
  the page against the live API, confirmed the call sheet renders with the
  correct day/crew-call/schedule data. Then blocked all network requests to
  the API and confirmed the app falls back to the IndexedDB-cached copy and
  visibly labels it "offline" / "showing cached revision" rather than
  silently reusing stale data. Separately confirmed the service worker
  registers and caches the app shell (`index.html`, `manifest.json`,
  `icon.svg`) into Cache Storage, so the page itself loads with no network,
  independent of the IndexedDB data layer.

## What's NOT verified / NOT built (be honest about the gap)

- No auth beyond a single shared dev token — no per-user accounts, no
  per-production share-link scoping for the public call-sheet URL.
- No Stripe/Twilio/Resend/Frame.io integration. `DistributionLog` exists as
  a table so "who has and hasn't opened today's revision" is answerable
  once sending is wired up, but nothing sends anything yet.
- No PDF export — the print stylesheet is real and was written, but not
  checked against an actual printed page.
- Not load-tested, not deployed anywhere, no CI configured yet.
- The service worker's own Cache Storage layer for API responses
  (`networkFirstWithCache` in `sw.js`) was written but not separately
  isolation-tested the way the IndexedDB layer was — the two layers
  overlap in practice (see `verify_pwa.py`, which deliberately blocks the
  service worker to test IndexedDB in isolation).

## Repo layout

```
backend/
  app/
    models/       SQLAlchemy models (production.py, call_sheet.py)
    schemas/       Pydantic request/response schemas
    routers/       FastAPI route handlers (I/O layer)
    services/      Business logic (revision publishing) — no FastAPI imports, unit-testable alone
    auth.py         Stub bearer-token dependency
    config.py       Settings (env-driven)
    database.py     Engine/session setup
    main.py         App entrypoint, route registration
  alembic/          Migrations (autogenerated initial schema in versions/)
  tests/            Pytest suite against a real Postgres test DB
frontend/
  index.html        The entire UI (inline CSS/JS, no build step)
  sw.js             Service worker (app-shell + API cache)
  manifest.json     PWA manifest
DESIGN.md            Data model rationale — read this before extending the schema
```

## Natural next steps

1. Decide real auth (who is "a production" — single-tenant per deploy, or
   multi-tenant with orgs/roles?) before building anything user-facing on top.
2. Wire one real distribution channel (Resend for email is the simplest)
   behind `DistributionLog`, since that's the feature that makes this a
   product rather than a form.
3. Add a partial unique index enforcing exactly one `is_current=True`
   revision per call sheet at the DB level (currently an app-layer
   invariant only — see the TODO in `models/call_sheet.py`).

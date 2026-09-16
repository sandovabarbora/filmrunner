# Pre-merge checklist

FR-5. What a PR touching `backend/` or `frontend/` must satisfy before the
founder merges it. Run this yourself before opening the PR; the PR
template links here and asks you to tick each box, so a skipped box is
visible on the PR itself, not silently merged. Gate roles (`security`,
`qa` in TEAM.md) also read from this file rather than improvising a check
each time.

## Security

- **No secrets in the diff.** No API key, token, password, or connection
  string in code, tests, fixtures, or committed `.env*` files. Config
  comes from `app/config.py` reading environment variables (see
  `backend/app/config.py`); Fly/Supabase secrets are set by the founder
  per the matching INBOX item, never hardcoded or logged.
- **Every non-public route requires auth.** A new backend route under
  `app/routers/` either depends on `require_principal` /
  `require_api_token` (see `backend/app/auth.py`) or is deliberately
  public (crew viewer, `GET /me/{token}`, health check) — say which, in
  the PR description. A route that also needs a production role goes
  through `authz.require_on` (`backend/app/authz.py`), not a bare
  principal check.
- **Input validation.** Request bodies are Pydantic models with real
  types (no bare `dict`/`Any` for user input); anything that becomes a
  DB query parameter goes through SQLAlchemy's parameter binding, never
  string-formatted SQL. IDs from the URL are validated as UUIDs before
  use.
- **No unescaped external data in HTML.** Frontend code never uses
  `dangerouslySetInnerHTML` (or raw `innerHTML`) on data that came from
  the API; React's default text rendering is the escape hatch, and
  `frontend/tests/test_smoke.py`'s
  `test_schedule_text_is_not_interpreted_as_html` is the standing
  regression test for this (FR-7).
- **Audit fields are server-set.** `created_by`, `published_at`, and
  similar fields on a write come from the authenticated principal and
  the server clock, never trusted from the request body (FR-7); a new
  write endpoint that sets one of these fields needs a test that a
  spoofed value in the body is ignored.
- **Dependency pins.** A new or bumped dependency in
  `backend/requirements.txt` or `frontend/package.json` is pinned to an
  exact version (`==`, not a range), and the PR says why it was added or
  changed.
- **No new account, payment, domain, or infrastructure change** ships in
  this PR; if the work needs one, it is an INBOX.md item instead (TEAM.md
  approval contract), and the PR either waits on it or ships the
  code-complete-but-inert path (see FR-16, FR-18 for the pattern: the
  feature 503s or no-ops with a clear message until the founder sets the
  secret).

## QA

- **Tests cover the change.** New backend behaviour has a `pytest` test
  under `backend/tests`; new frontend behaviour that touches the real
  API/build has a Playwright test under `frontend/tests`. A doc-only or
  research PR has no code to test — say so instead of adding a
  placeholder test.
- **The failure case is covered, not just the happy path.** Every backlog
  item's `dod` names one (network loss, missing auth, bad input, a
  provider timeout, a not-found link); the PR's tests exercise it, not
  just describe it.
- **CI is green on the PR's own head**, not just locally: branch and PR
  title conventions (`scripts/check_conventions.py`), company docs format
  (`scripts/check_company_docs.py` if `BACKLOG.md`/`INBOX.md` changed),
  backend tests, and the frontend build + smoke tests (`.github/workflows/ci.yml`).
  A red check is not "probably fine" — re-run or fix before asking for
  merge.
- **Verified against something real when the dod says so.** A dod
  bullet that names a real build, a real API, or a real browser is not
  satisfied by a mock alone; if this environment cannot do that (e.g. a
  blocked Playwright browser download, blocked egress to a third party),
  the PR says exactly what was and was not verified and why, rather than
  claiming full verification.

## Using this list

- Tick each box in the PR template as you satisfy it; leave a box
  unchecked with a one-line reason if it does not apply (e.g. "no
  non-public route added").
- A PR that ships a feature gated on an INBOX item still needs every box
  above ticked for the code it does add — the gate is about what shipped,
  not an excuse to skip the checklist.
- This list changes by PR like anything else in `docs/`; if a gate role
  or a shift finds a gap (a bug class this list would have caught),
  update this file in the same PR as the fix.

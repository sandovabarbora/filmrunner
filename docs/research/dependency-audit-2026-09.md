# Dependency vulnerability audit, 2026-09-25

FR-91. Scope: `backend/requirements.txt` (`pip-audit`) and
`frontend/package.json`/`package-lock.json` (`npm audit`), both run
directly against this sandbox's own registry access (both PyPI and the
npm registry were reachable this shift — no GitHub Actions job needed;
if a future re-run finds either registry blocked, that must be recorded
here explicitly rather than reporting a clean scan, per this item's own
failure case).

## Method

- `pip install pip-audit` (2.10.1) then `pip-audit -r backend/requirements.txt -f json`,
  against a fresh venv (`/tmp/venv-fr91`) so the running scan never touches
  the checked-out tree's own state.
- `npm audit --json` from `frontend/` against the committed `package-lock.json`.
- For every finding, checked whether the advisory's own `fix_versions`
  stays reachable without changing which major version of the package
  (or, where a major bump was the only path, whether the specific bumped
  version still passes this repo's own test suite exercising that
  dependency) before treating a bump as safe.
- After each backend bump: created a fresh local Postgres role/db+test-db
  (neither existed this session), ran the full Alembic migration chain,
  then the full backend suite in the bumped venv. All results below are
  from that same venv, not assumed from the advisory text alone.

## Backend (`pip-audit`)

Before: 121 known vulnerabilities across 6 pinned packages.

| Package | Before | After | Status |
|---|---|---|---|
| `python-dotenv` | 1.0.1 | **1.2.2** | fixed — same major, 153/153 backend tests pass |
| `PyJWT` | 2.9.0 | **2.13.0** | fixed — same major, closes 12 advisories (incl. PYSEC-2025-183 with no listed fix version, superseded by later 2.x releases), 153/153 pass |
| `python-multipart` | 0.0.12 | **0.0.31** | fixed — within `fastapi==0.115.0`'s own declared range (`>=0.0.7`, no upper bound; checked via the wheel's `METADATA`), closes 14 advisories, 153/153 pass |
| `pytest` | 8.3.3 | *(unchanged)* | **not fixed — genuinely breaking, documented.** First attempted a bump to 9.0.3: `backend/requirements.txt`'s own suite passed 153/153 against it in isolation, but CI installs `-r backend/requirements.txt -r frontend/tests/requirements.txt` together (`.github/workflows/ci.yml`), and `frontend/tests/requirements.txt` pulls in `pytest-playwright==0.5.2`, whose own `METADATA` pins `pytest<9.0.0,>=6.2.4` — a real, unresolvable conflict (pip's resolver rejected it outright: "Cannot install pytest==8.3.3 and pytest==9.0.3 because these package versions have conflicting dependencies"), caught only after CI actually failed on this PR's first push (**check run `ci`, run [36140568865](https://github.com/sandovabarbora/filmrunner/actions/runs/36140568865)** — the local backend-only venv used for the first verification pass never installed `frontend/tests/requirements.txt`, so it couldn't see this). Reverted to 8.3.3, re-verified against the real combined `pip install -r backend/requirements.txt -r frontend/tests/requirements.txt` CI uses (153/153 backend tests still pass). Closing PYSEC-2026-1845 (a local `/tmp/pytest-of-{user}` directory-name DoS/privilege risk, low real-world impact for a CI/dev-only tool) needs a coordinated `pytest`+`pytest-playwright` upgrade (latest `pytest-playwright` is 0.9.0, itself tied to a newer `playwright` than this repo's pinned `1.47.0`) — filed as a follow-up, not attempted here. |
| `pypdf` | 5.1.0 | **6.19.0** | fixed — also a semver-major bump, closes 77 advisories (`backend/app/services/call_sheet_pdf.py` calls `PdfReader`/`extract_text` directly on **untrusted user-uploaded PDFs**, FR-57's old-call-sheet import — this is exactly the attack surface these advisories target: crafted PDFs causing memory exhaustion or infinite loops while parsing). Ran `tests/test_call_sheet_pdf.py` in isolation first (3/3 pass, including the no-text-layer/scan fixture), then the full suite (153/153) — real evidence this specific usage still works, not just an unread major-version label. `frontend/tests/requirements.txt` pins `pypdf` separately (for `test_pdf_e2e.py`'s own `PdfReader`/`.pages`/`extract_text()` calls, the same stable API) — bumped there too, to the same 6.19.0, and sanity-checked the read/write round trip directly; kept in sync rather than left to drift. |
| `starlette` | 0.38.6 | *(unchanged)* | **not fixed — genuinely breaking, documented.** Every fix starts at `0.40.0`, but `fastapi==0.115.0`'s own `METADATA` pins `starlette<0.39.0,>=0.37.2` — 0.38.6 is already the newest version that pin allows, so closing this requires a coordinated `fastapi` upgrade too. Checked how far: PyPI's newest `fastapi` is `0.141.1`, ~26 minor releases ahead of the pinned `0.115.0`. That is a real framework-upgrade project (API surface, deprecations, its own regression pass), not a same-shift dependency bump, so it is **not attempted here**. Remaining advisories: PYSEC-2026-1943/1941 (unbounded multipart form-field buffering — mitigated in practice today by `python-multipart`'s own size handling and this app's endpoints not accepting arbitrary large text fields, but not a substitute for the real fix), PYSEC-2026-161/248 (unvalidated `Host`/path header reflected into `request.url`), PYSEC-2026-2281/2280 (Windows-only `StaticFiles`/`HTTPEndpoint` issues — this app is deployed on Fly.io Linux, so these two are not exploitable in production), PYSEC-2026-249 (`max_fields`/`max_part_size` silently unenforced on non-multipart bodies). **Follow-up:** a dedicated `fastapi`+`starlette` upgrade item, scoped and tested on its own, not bundled into a dependency-audit PR. |

After this PR: 0 known vulnerabilities in `python-dotenv`, `PyJWT`,
`python-multipart`, `pypdf`. `pytest`'s and `starlette`'s advisories
remain open, tracked above — `pytest` blocked on a coordinated
`pytest-playwright` (and likely `playwright`) upgrade, `starlette`
blocked on a `fastapi` upgrade.

Full backend suite: **153/153** passing on the final bumped
`requirements.txt`, against a real local Postgres (fresh role/db, full
Alembic migration chain from a dropped-and-recreated database, not
`create_all`) — verified both in isolation and against the exact combined
install CI runs (`pip install -r backend/requirements.txt -r
frontend/tests/requirements.txt`), after the first version of this PR's
`pytest` bump broke that combined install and CI caught it (see the
`pytest` row above).

## Frontend (`npm audit`)

6 vulnerabilities (3 moderate, 2 high, 1 critical) across 6 packages, all
transitive from `vite`/`vitest`/`xlsx`:

| Package | Installed | `npm audit`'s fix | Status |
|---|---|---|---|
| `vite` | 5.4.11 | `vite@8.3.1` (`isSemVerMajor: true`) | **not fixed — breaking, documented.** 3 advisories (path traversal in optimized-deps `.map` handling, an NTLMv2 hash-disclosure path via `launch-editor` on Windows, an `fs.deny` bypass on Windows). Windows-specific findings do not apply to this app's Linux dev/CI environment; the `.map`-handling path-traversal finding is a dev-server-only issue (`vite dev`), not present in the built static output this app actually ships. A `vite` 5→8 bump changes the build pipeline (`vite-plugin-pwa`, the project's own Vite plugin config) and needs its own regression pass, not a same-shift bump. |
| `vitest`, `@vitest/mocker`, `vite-node` | 2.1.9 (indirect) | `vitest@5.0.2` (`isSemVerMajor: true`) | **not fixed — breaking, documented.** The critical finding (arbitrary file read/execute via the Vitest UI server) requires the UI server, which this project never runs (`npm test` uses `vitest run`, no `--ui` flag anywhere in `package.json` or CI); still a real gap if anyone ever runs `vitest --ui` locally. `vitest` 2→5 is a major test-runner upgrade, own item. |
| `xlsx` | 0.18.5 | **none available** (`fixAvailable: false`) | **not fixed — no fix exists on the npm registry.** Two advisories (prototype pollution, ReDoS). SheetJS's own advice is to install their CDN-hosted build (`https://cdn.sheetjs.com/...`) instead of the abandoned npm package — that is a supply-chain and build-tooling change (a non-npm-registry install source), out of scope for a dependency-pin-bump item and worth its own scoped decision (ADR or a build-config change), not a silent registry swap here. |

Full detail: `frontend/scripts/` has no equivalent audit-runner script
yet; this pass was run directly (`npm audit --json`), not scripted, since
one `npm audit` invocation is the whole check and there is nothing to
automate beyond what CI can already run on every PR if wanted later.

## What changed in this PR

`backend/requirements.txt`: `python-dotenv`, `PyJWT`, `python-multipart`,
`pytest`, `pypdf` bumped as above. No frontend files changed — every
frontend finding needs a breaking upgrade or has no fix at all.

## Follow-ups (not done this shift, named so they aren't lost)

- A scoped `fastapi` + `starlette` upgrade.
- A scoped `pytest` 9.x + `pytest-playwright` (and likely `playwright`,
  since `pytest-playwright`'s newer releases track newer `playwright`
  pins) upgrade — low urgency (test-only, low real-world impact
  advisory), but needed to close the last open backend finding.
- A scoped `vite` 8.x upgrade (dev-server-only findings, Windows-only
  findings do not affect this deployment, but the path-traversal one is
  real for anyone running `vite dev` exposed beyond localhost).
- A scoped `vitest` 5.x upgrade (only exploitable if `--ui` is ever run;
  not used today).
- A decision on `xlsx`: move to SheetJS's own CDN-hosted package, find an
  alternative library, or accept the risk with a documented reason —
  needs the founder or tech-lead to pick, not silently patched here.

## Resolution: the 10 `pyjwt` CVEs (FR-117, 2026-10-01)

FR-110's 2026-09-30 09:00 shift (PR #278, still open at the time) flagged
"10 new unrelated `pyjwt` CVEs" in its own pip-audit re-run but never
filed or recorded them — this section closes that gap.

### Re-run against `main` (`PyJWT[crypto]==2.13.0`, unchanged since FR-91)

`pip-audit -r backend/requirements.txt` from a fresh venv now reports
**13** `pyjwt` CVE IDs, not 10 — the advisory database grew between
2026-09-30 and 2026-10-01 (not a re-count error; same method as FR-91/
FR-110, a fresh venv, no caching). Listed here by ID so a future diff
against this list is possible:

| CVE | Fix version |
|---|---|
| CVE-2026-102274 | 2.14.0 |
| CVE-2026-101917 | 2.14.0 |
| CVE-2026-102273 | 2.14.0 |
| CVE-2026-102269 | 2.14.0 |
| CVE-2026-102267 | 2.14.0 |
| CVE-2026-102268 | 2.14.0 |
| CVE-2026-102272 | 2.14.0 |
| CVE-2026-102271 | 2.14.0 |
| CVE-2026-102265 | 2.14.0 |
| CVE-2026-102266 | 2.14.0 |
| CVE-2026-102270 | 2.14.0 |
| CVE-2026-101918 | 2.15.0 |
| CVE-2026-103001 | *(none listed — `options` dict mutated in place when `verify_signature` is falsy)* |

None of this app's own code calls `jwt.decode`/`jwt.decode_complete` with
`verify_signature` falsy (`app/auth.py:66` is the only call site, always
full verification against the JWKS signing key), so CVE-2026-103001 does
not reach this app's own attack surface even before any fix — checked by
reading the call site directly, not assumed from the advisory's title.

### Fix

Bumped `PyJWT[crypto]` 2.13.0 → **2.15.1** (latest on PyPI as of this
run, one patch release past 2.15.0, the newest version either advisory
above names) on a throwaway branch. Re-ran `pip-audit`: **0** `pyjwt`
findings afterward, including CVE-2026-103001, which has no `fix_versions`
listed in the advisory data but is gone from the post-bump scan — the
live scan is the source of truth here, not the advisory's own (incomplete)
metadata.

Verified safe to ship: built a fresh local Postgres role/db, ran the full
Alembic migration chain from scratch, then the full backend suite —
**153/153 pass**, same count as FR-91/FR-110's baseline, so the bump is
behaviour-neutral for this repo's own JWT usage (`app/auth.py`'s single
`jwt.decode` call site, HS256/RS256 verification against Supabase's
JWKS). No other backend package touched.

`starlette` (0.38.6, still blocked on a `fastapi` upgrade, FR-91/FR-100's
open PR #249) and `pytest` (now 9.1.1 per FR-110's PR #278, still open —
once merged this row should re-check clean) are unchanged by this item
and remain tracked in their own rows above; this item scoped to `pyjwt`
only, per its own dod.
## Re-verification and fix (FR-111, 2026-09-30)
FR-91 documented every frontend finding as "not fixed" and none had been
attempted since. This shift attempted the breaking `vite`/`vitest` bump
`npm audit` recommends, on a throwaway branch, per this item's own dod.
Before (`npm audit`, re-run this shift against the committed lock file —
already two more transitive findings than FR-91's original 6, all still
rooted in the same `vite`/`vitest`/`xlsx` chain): 8 vulnerabilities (4
moderate, 3 high, 1 critical) across `@vitest/mocker`, `brace-expansion`,
`esbuild`, `fast-uri`, `vite`, `vite-node`, `vitest`, `xlsx`.
Bumped `vite` 5.4.11→**8.3.1**, `vitest` 2.1.9→**5.0.2**, `vite-plugin-pwa`
0.21.1→**1.3.0** (peer-required for `vite` 8; confirmed on the npm registry
its `peerDependencies` already lists `vite: "... || ^8.0.0"`), and
`@vitejs/plugin-react` 4.3.4→**6.1.1** (same reason, peer-requires
`vite: "^8.0.0"`) together — attempting `vite`/`vitest` alone left the
existing plugin versions unable to resolve against the new `vite` major.
Verified for real, not assumed from a clean `npm install` alone:
- `npm run typecheck` — clean.
- `npm run build` — succeeds; output is a working `dist/` (same four
  entries, `PWA v1.3.0` precache manifest generated). One new advisory
  notice, not an error: Vite's own `configLoader: 'native'` (a future
  default) warns that `vite.config.ts`'s use of `__dirname` (line 86) will
  need `import.meta.dirname` eventually — noted here as a follow-up, not
  fixed in this PR, since the build is not broken today.
- `npm test` (vitest unit suite) — **53/53 pass**, unchanged from the
  pre-bump baseline (also re-confirmed 53/53 on the untouched `main`
  branch immediately before this attempt, so this is a real before/after,
  not an assumption).
- Full Playwright E2E suite (`frontend/tests/`, real build, real
  uvicorn+Postgres API, a fresh local Postgres role/db and the full
  Alembic migration chain run from scratch since neither existed this
  session) — **75/77 pass**. The 2 failures
  (`test_locations_e2e.py::test_add_location_with_real_address_shows_resolved_place_name`,
  `::test_day_without_location_says_what_is_missing_and_picking_one_fills_sunrise`)
  are the same pre-existing Nominatim-egress 403 every prior shift on this
  suite has hit (confirmed live in this run's own log: `Geocoding failed
  for '...': 403 Forbidden`), not caused by this dependency bump.
Result: `npm audit` after the bump reports **1 finding** (`xlsx`, high,
`fixAvailable: false`) — the `vite`/`vitest` bump alone resolved
`@vitest/mocker`, `brace-expansion`, `esbuild`, `fast-uri`, `vite`,
`vite-node`, and `vitest` (7 of the 8 open findings), because the newer
majors pull in already-patched versions of those transitive deps too.
Opened as a real PR per this item's dod (green build/typecheck/tests, not
a broken one forced through).
`xlsx` re-checked against the npm registry and the advisory database
(`GHSA-4r6h-8v6p-xvw6` prototype pollution, `GHSA-5pgg-2g8v-p4x9` ReDoS):
the registry's newest published version is still **0.18.5** — unchanged
since FR-91's 2026-09-25 pass and still the currently-installed version;
both advisories' fixed ranges (`>=0.19.3`, `>=0.20.2`) were never
published to npm. FR-91's own conclusion stands: SheetJS only ships the
fix through their CDN-hosted build, not the npm registry, which would be a
non-npm-registry install source (a build-tooling/supply-chain decision,
not a dependency-pin bump) — still not attempted here, still needs the
founder or tech-lead to pick an option from FR-91's own follow-up list.
**Accepted risk, dated re-check trigger: re-run `npm view xlsx versions`
at the next dependency-audit pass; if `>=0.19.3` ever appears on the
registry, this becomes a same-shift bump like `vite`/`vitest` was here.**

## Failure case (per this item's own dod)

Both scanners reached their advisory databases successfully this run —
PyPI and the npm registry were both reachable from this sandbox (checked
directly with `curl` before running either audit: `200` from
`pypi.org/simple/...`, `200` from `registry.npmjs.org/react`). If a
future run finds either blocked, `pip-audit`/`npm audit` fail loudly
(non-zero exit, no report) rather than returning an empty result that
could be misread as "clean" — confirm the exit code, not just the
absence of findings, before recording a scan as clean.

## FR-100 resolution, 2026-09-28: fastapi/starlette upgrade closes the `starlette` CVEs

`fastapi` bumped `0.115.0` → `0.141.1` (latest on PyPI as of this date).
`starlette` was not pinned directly — it floats to whatever `fastapi`'s
own `METADATA` allows — and resolved to `1.7.0`, past the `0.40.0` floor
every open advisory needed (`starlette` itself renumbered its versioning
scheme somewhere in that range; the actual jump is roughly 26 `fastapi`
minors, as FR-91 estimated, not a small point release).

`pip-audit -r backend/requirements.txt` after the bump: `starlette`
carries zero findings (all of FR-91's listed advisories —
PYSEC-2026-1943, 1941, 161, 248, 2281, 2280, 249 — are gone). Only the
already-documented, out-of-scope `pytest` finding (PYSEC-2026-1845,
blocked on a coordinated `pytest-playwright`/`playwright` upgrade per
FR-91) remains.

Verification, real not assumed:

- Full backend suite: **153/153**, twice — once against a fresh local
  Postgres role/db with the full Alembic migration chain run from empty
  (neither existed this session), once more after re-applying the chain
  post-bump. No test changed; nothing in `app/` broke.
- The exact combined install CI uses (`pip install -r
  backend/requirements.txt -r frontend/tests/requirements.txt`) succeeds
  cleanly in a fresh venv — no resolver conflict, unlike FR-91's `pytest`
  attempt.
- Per this item's own failure-case bullet (a bump that passes backend
  unit tests but changes response/error behaviour the PWA depends on):
  ran the full frontend Playwright E2E suite (`frontend/tests`, 77 tests)
  against a real build and the bumped backend (uvicorn spawned from the
  same bumped venv, `sys.executable`) — **75/77 pass**; the 2 failures
  are `test_locations_e2e.py`'s real-Nominatim geocoding tests, both
  failing on the same `403 Forbidden` from this sandbox's egress proxy
  that every prior shift touching that file has documented (FR-18/19/74
  notes above) — a standing sandbox network gap, not a response-shape
  change from this bump; confirmed by the error itself (an HTTP 403 from
  `nominatim.openstreetmap.org`, not an assertion about the app's own
  API response).

New deprecation warnings surfaced (not failures, no dod bullet requires
fixing them, noted so a future shift doesn't re-discover them from
scratch): `status.HTTP_422_UNPROCESSABLE_ENTITY` and
`HTTP_413_REQUEST_ENTITY_TOO_LARGE` (used in
`app/routers/call_sheets.py`, `app/routers/productions.py`) are renamed
in this starlette version to `..._CONTENT`; both old names still resolve
to the same numeric status code and still pass every test, so left
as-is. `starlette.testclient` warns that using it with `httpx` directly
is deprecated in favour of a separate `httpx2` package — the test suite
uses FastAPI's own `TestClient` wrapper, not `starlette.testclient`
directly, so no code change follows from this warning either; flagged
for whoever eventually revisits test tooling.

No migration, no API contract change, no `app/` code change — this PR is
the version bump alone. Backend changed: deploy needed (pins only).

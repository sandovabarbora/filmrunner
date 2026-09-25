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

## Failure case (per this item's own dod)

Both scanners reached their advisory databases successfully this run —
PyPI and the npm registry were both reachable from this sandbox (checked
directly with `curl` before running either audit: `200` from
`pypi.org/simple/...`, `200` from `registry.npmjs.org/react`). If a
future run finds either blocked, `pip-audit`/`npm audit` fail loudly
(non-zero exit, no report) rather than returning an empty result that
could be misread as "clean" — confirm the exit code, not just the
absence of findings, before recording a scan as clean.

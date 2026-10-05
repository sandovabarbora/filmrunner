# FR-131 — post-merge-spree flake baseline (2026-10-05, 14:11 shift)

Role: qa. Goal per the item: run the full backend + frontend + E2E suite,
fresh, three consecutive times, to rule out an order-dependent or
merge-combination regression that no single PR's own CI run (each tested
against a different base) could have caught after the founder's 2026-10-02
twenty-PR merge spree (`STATUS.md`).

## What "fresh" means here

Each of the three runs below started from a dropped-and-recreated Postgres
role and both databases (`filmrunner`, `filmrunner_test`) — not a reused
schema — then:

1. `alembic upgrade head` against the empty `filmrunner` database.
2. `python -m pytest backend/tests` against `filmrunner_test` (its own
   `conftest.py` builds the schema with `Base.metadata.create_all`,
   independent of the Alembic check above — matching how the existing suite
   already separates the two).
3. `npm install && npm run build` (frontend, from the already-installed
   `node_modules` — not wiped between runs, since the dod does not ask for a
   from-scratch `node_modules` the way FR-123's exploratory pass did).
4. `npm run typecheck`, then `npm test` (`vitest run`).
5. `python -m pytest frontend/tests` — the Playwright E2E suite, each run
   spawning its own fresh `uvicorn` subprocess per `tests/conftest.py`.

Branch tested: `main` at `1fed456` (`chore(state): shift 2026-10-05 13:11`,
PR #355) — the latest merged commit at shift start. None of the five open
PRs at the time (#346/#348/#350/#352/#354) are merged into this commit, so
their added tests are not part of this baseline; re-running this baseline
after they merge would be reasonable but is not this shift's scope.

Chromium: this sandbox has no outbound access to download Playwright's
pinned revision, so `frontend/tests/conftest.py`'s own fallback
(`resolve_chromium_launch_args`, added for exactly this gap) launched the
pre-installed `/opt/pw-browsers/chromium` build instead — the same
documented, pre-existing gap earlier shifts (FR-74, FR-123) have noted, not
new to this run.

## Results

| Run | Alembic (empty → head) | Backend pytest | `npm run build` | `npm run typecheck` | `vitest run` | Playwright E2E |
|---|---|---|---|---|---|---|
| 1 | clean, 20 migrations | 153 passed | clean | clean | 66 passed | 90 passed, 3 skipped |
| 2 | clean, 20 migrations | 153 passed | clean | clean | 66 passed | 90 passed, 3 skipped |
| 3 | clean, 20 migrations | 153 passed | clean | clean | 66 passed | 90 passed, 3 skipped |

Every run produced byte-identical pass/skip counts. No test passed in one
run and failed in another; no test's outcome varied at all across the three
runs.

The 3 skipped tests are the same three in all three runs, and are a known,
documented gap, not a flake: `frontend/tests/test_locations_e2e.py`'s three
`_NEEDS_LIVE_NOMINATIM`-marked tests skip themselves when the live
Nominatim geocoding service is unreachable (this sandbox's egress proxy
blocks it; `WebSearch` works, direct `WebFetch`/`curl` to most external
domains does not — same gap `STATUS.md` has logged under "blockers" since
2026-09-22).

## Conclusion

No order-dependent or merge-combination regression found across three fresh
runs. Per the dod's own failure case: no test failed in exactly one of the
three runs, so nothing is filed as a new backlog item from this pass. The
2026-10-02 merge spree does not show a hidden interaction bug in this
baseline.

FR-131 set to `done` — the dod's own three-run record is the whole
deliverable; no backend/frontend code was changed, no deploy needed.

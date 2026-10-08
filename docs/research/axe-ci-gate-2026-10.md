# Automated axe-core accessibility scan wired into CI (FR-127), 2026-10-05

FR-63 (2026-09-22) already put an axe-core pass into `frontend/tests/test_a11y.py`, and that
file already runs inside `ci.yml`'s "Frontend smoke" step (`python -m pytest frontend/tests -q`),
gated the same `RUN_HEAVY` way FR-102/FR-122 established — it is skipped only on a docs-only PR
and runs (gating, not just reporting) on every PR that touches code. So two of this item's three
dod bullets were already true going in; this shift's real work was the third, and a genuine gap
the failure-case check surfaced along the way.

## What was already covered, verified by reading the existing suite

- Public sheet: `test_crew_sheet_demo` (demo, English and Czech).
- Personal crew link: `test_personal_link_day_screen_and_crew_tab`'s own `crew_view` page.
- Already a CI-gating step, not a report: `ci.yml`'s "Frontend smoke" step runs
  `frontend/tests` under `RUN_HEAVY` on every non-docs-only PR; `audit()` asserts, it doesn't print-and-pass.

## What was missing: the crew-list PDF-source page

`frontend/src/editor/crewPrint.ts`'s `crewPrintHtml`/`crewPrintWindow` build the crew-list print
view as its own plain document (own `<style>`, own markup, opened in a new window/blob URL) —
never the app's own DOM, so no existing audit touched it. Added `test_crew_list_print_view` to
`frontend/tests/test_a11y.py`: imports crew (with a head-of-department) and one cast member in a
real editor session, clicks `#printCrew`, captures the popup via `page.context.expect_page()`,
and runs the same `audit()` against it. Passes clean (0 violations).

## The failure-case check found a real gap, now fixed

FR-127's own dod says: reintroduce one of FR-82's fixed issues locally and confirm the new CI
step fails loudly on it, then revert. Reintroducing FR-82's `#langToggle` `aria-label` mismatch
(`aria-label="Přepnout do češtiny"` on a button whose visible text is "Čeština") and rebuilding
showed **the existing `audit()` reported 0 violations** — it did not fail.

Root cause, confirmed by inspecting `axe-core`'s own rule list
(`require('axe-core').getRules().find(r => r.ruleId === 'label-content-name-mismatch')`): the
rule behind *both* of FR-82's fixes (the `langToggle` aria-label and the Copy button's icon
glyph) is tagged `experimental` and ships `enabled: false`. A plain `axe.run(document, {
resultTypes: ['violations'] })` — what `audit()` called — silently skips every disabled rule,
including this one, at `impact: 'serious'`. FR-82's own note says it "re-ran
`frontend/tests/test_a11y.py`'s axe pass" to confirm the fix — that re-run never actually
exercised this rule; the regression this dod asks to simulate could land today and stay green.

Fix: `audit()` now explicitly enables the rule —
`rules: { 'label-content-name-mismatch': { enabled: true } }` — alongside the existing
`resultTypes: ['violations']`. Re-ran the reintroduced bug: fails loudly
(`label-content-name-mismatch (serious) on ['#langToggle']`). Reverted the bug (confirmed via
`git diff` showing no change to `App.tsx`), re-ran clean: 7/7 `test_a11y.py` passes.

## Verification run, this shift

Local Postgres 16, `npm run build`, pinned-Chromium fallback (this sandbox's pre-installed
revision, same known gap prior shifts noted in `conftest.py`):

- `frontend/tests/test_a11y.py`: 7/7 (6 existing + the new crew-list print view test).
- `frontend/tests` (full E2E suite): 91 passed, 3 skipped.
- `npm run typecheck` / `npm test`: clean, 66/66.
- `backend/tests`: 153/153.
- `scripts/tests` (company-doc/convention checkers): 81/81.

## Not done this shift

CI's own `RUN_HEAVY` gating already gives this a real CI run on every code PR; no `ci.yml` change
was needed since FR-63 already wired the step. Only `label-content-name-mismatch` was explicitly
re-enabled — other `experimental`-tagged axe rules were not surveyed and may carry the same gap;
worth a dedicated pass if a future shift wants to check which other disabled-by-default rules this
suite silently skips.

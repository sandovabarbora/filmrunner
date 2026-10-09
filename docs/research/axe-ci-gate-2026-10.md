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

## FR-157 (2026-10-09): surveying every other disabled-by-default rule

FR-127 enabled exactly one of the sixteen rules the pinned `axe-core` (4.10.x) ships
`enabled: false`, and flagged — but never checked — whether the other fifteen carry the same
silent-skip gap on this app's own four audited screens (public sheet, personal crew link,
editor, crew-list print view). This pass enumerates all sixteen via `axe.getRules()` (not just
the `experimental`-tagged ones — the dod's own wording), judges each for relevance, and enables
the ones that are both relevant and workable as a hard CI gate here.

### The full list, and the call on each

| Rule | Verdict | Why |
|---|---|---|
| `label-content-name-mismatch` | already on (FR-127) | — |
| `table-fake-caption` | **enabled, found a real issue** | the crew-list print view's department-divider row (`<th colspan="3">`) was structurally identical to axe's "fake caption" pattern (a one-cell row spanning every column, as the table's first row) — true regardless of intent. Fixed by giving the table real `<thead>` column headers (Name/Position/Phone), which also happens to be a genuine, separate gap (the table had no column headers at all); the free-floating "Crew list · printed …" line was moved into a proper `<caption>` at the same time. |
| `css-orientation-lock` | enabled, clean | this is a mobile PWA read in the field; no CSS orientation lock exists on any of the four screens — kept on as a regression gate. |
| `focus-order-semantics` | enabled, clean | ADs fill forms fast, often by keyboard; no non-interactive-role-in-focus-order issue found — kept on as a regression gate. |
| `identical-links-same-purpose` | enabled, clean | the personal-links list repeats an "Open" link per crew member with a different `href` each time — the exact shape this AAA rule checks — but axe did not flag it (each link's surrounding context differs enough); kept on as a regression gate in case that context is ever lost. |
| `p-as-heading` | enabled, clean | the app already uses real `<h1>`/`<h2>` throughout, no `<p>` styled to fake a heading found — kept on as a regression gate. |
| `target-size` | enabled, clean | WCAG 2.2 AA, directly relevant (this is read on a phone, one-handed, in the field); no touch target under 24px found on the four screens today — kept on as a regression gate against a future small icon-button. |
| `td-has-header` | enabled, clean | relevant in principle for the schedule table as it grows; none of today's tables exceed the rule's own 3×3 threshold — kept on as a regression gate. |
| `color-contrast-enhanced` | **left off — real gap, not a false positive, but unworkable as a hard gate today** | WCAG AAA (7:1), not the AA (4.5:1) this product has targeted so far (the always-on `color-contrast` rule already passes everywhere). Firing broadly and consistently: the base secondary-text color (`#6e685f` on `#f7f4ee`) sits at 5.02:1 on every screen audited (50 node instances on the demo sheet alone), and `#status`'s green sits at 6.77:1 — a systemic design-system gap, not an isolated bug a targeted fix could close. Enabling it today would turn every existing screen red for a bar this product has never committed to. Left disabled; worth a dedicated design-system color pass if AAA ever becomes the target, not a reactive fix here. |
| `hidden-content` | **left off — needs a config change this suite doesn't make** | tagged `review-item`: by axe-core's own design this rule only ever reports through the `incomplete` result type, never `violations` — this suite's `audit()` only requests `resultTypes: ['violations']` (so BLOCKING, which only inspects `violations`, would never see it fire) and widening that would also pull in every other rule's `incomplete`/needs-review noise, not just this one. Exactly the "needs a config option `axe.run()` doesn't pass today" case the item's own dod names. |
| `landmark-complementary-is-top-level` | left off — deprecated, already covered | axe-core tags it `deprecated`. The app's one `<aside>` (`App.tsx`'s "tomorrow" panel) already sits at top level and passes it, and the always-on `region`/`landmark-one-main` rules already gate general landmark structure on every screen (confirmed firing independently on the crew-list print view in this same run). |
| `duplicate-id` | left off — deprecated, superseded | axe-core tags it `deprecated`; `duplicate-id-aria`, the non-deprecated replacement, is already `enabled: true` by default and already gates this suite. |
| `duplicate-id-active` | left off — deprecated, superseded | same reasoning as `duplicate-id`. |
| `aria-roledescription` | left off — not applicable | deprecated, and `grep -rn "aria-roledescription" frontend/src` is empty — the app never sets this attribute. |
| `audio-caption` | left off — not applicable | deprecated, and the app has no `<audio>` element anywhere (`grep -rn "<audio" frontend/src frontend/*.html` is empty). |
| `meta-refresh-no-exceptions` | left off — not applicable | the app never uses `<meta http-equiv="refresh">` anywhere (grep confirmed). |

### Verification run, this shift

Local Postgres 16, `npm run build`, this sandbox's pre-installed Chromium (`chromium-1194`):

- `frontend/tests/test_a11y.py`: 7/7 (the crew-list print view's `table-fake-caption` finding
  reproduced against the pre-fix markup, then confirmed fixed — not just a blind rule-enable).
- `frontend/tests` (full E2E suite): 96 passed, 3 skipped.
- `npm run typecheck` / `npm test`: clean, 71/71.
- `backend/tests`: 248/248 (no backend file touched; run anyway per the pre-merge checklist).
- `scripts/check_company_docs.py docs/company`: clean.

### Not done this pass

`identical-links-same-purpose`, `css-orientation-lock`, `focus-order-semantics`, `p-as-heading`,
`target-size` and `td-has-header` are enabled but have never yet caught a real issue on this
app — unlike `label-content-name-mismatch` (FR-127) and `table-fake-caption` (this item), there
is no confirmed case of them firing loudly on a reintroduced bug here. Worth a deliberate
"reintroduce and confirm red" pass for each if a future shift wants the same confidence FR-127
and FR-157 have for the two rules that have actually found something.

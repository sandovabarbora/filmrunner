# Keyboard-only navigation, 2026-10-05 (FR-126)

axe-core (FR-63) explicitly cannot verify actual keyboard operability (WCAG 2.1.1
Keyboard, 2.1.2 No Keyboard Trap) — it checks names, roles, structure and contrast, not
whether a control can be reached and operated with Tab/Shift+Tab/Enter/Escape alone.
Nothing in this repo had ever driven the crew sheet, a personal link, or the editor
using only a keyboard. Test: `frontend/tests/test_keyboard_nav.py`.

Screens covered, per the item's own dod: the crew sheet (demo, English and Czech), a
crew member's personal link, the editor's Crew tab, and the editor's day screen
(draft, with a scene and times filled in).

## Method

`walk_keyboard()` Tabs forward from wherever focus currently is, twice in a row
(through the end of the document and once more — the dod's own repeat), and for every
focused control asserts: a real, visible focus indicator (`outline-style` not `none`
with non-zero width, or a `box-shadow`, computed live — not assumed from the
stylesheet), and no control ever getting stuck repeating itself (a trap). Reaching the
end of the document (focus lands on `<body>`) within a bounded number of presses, on
both laps, is what proves there is no trap — not a specific expected element count,
since where the walk starts depends on what the test already clicked to get there.

## Result

**Zero keyboard-operability defects on any of the four screens.** No app code change
was needed — every interactive control in `frontend/src` already carries a
`:focus-visible` rule (`styles.css`, `editor/editor.css`) covering inputs, buttons,
selects, textareas and the language toggle, and nothing in the codebase holds focus
inside an overlay/dialog while open (checked directly: no `<dialog>`, no focus-trapping
modal exists anywhere under `frontend/src`), so the dod's own named failure case (an
intentionally focus-holding dialog, e.g. a crew-import one) has nothing to exercise
today. The crew-import flow (`crewImport.ts`/`crewFileImport.ts`) is an inline textarea
and file picker on the Crew tab itself, not an overlay.

## Two test-design pitfalls found and resolved (in the test, not the app)

Verifying the test itself before trusting a clean result surfaced two real quirks that
would otherwise have produced false failures or a false sense of security:

1. **"Wrap lands back at the first control" is not a safe assertion when the walk
   starts mid-page.** A real browser's "sequential focus navigation starting point"
   follows the last interaction (even a scripted `.click()`), not the top of the
   document — `document.activeElement.blur()` does not reset it. The first draft of
   this test asserted the control after wraparound equalled the walk's own first
   control, which failed on the editor (the walk starts after clicking into a tab, so
   the *document's* first control — the header logo link — is earlier than the walk's
   own start). Fixed by walking to the end twice and only requiring the end to be
   reached within budget each time, never asserting a specific restart element.
2. **A native `<input type="date">` keeps `document.activeElement` on the same node for
   up to three consecutive Tab presses** while Tab moves between its internal
   year/month/day segments — true in every browser, not a trap, and not something our
   CSS controls. The segment Chromium calls "focused" after the first Tab into the
   control does not keep re-asserting `:focus-visible` on the later internal-segment
   moves either, even though the control still shows a native highlighted segment to a
   sighted keyboard user — not visible to `getComputedStyle`, so this is a limit of the
   automated check, not a real missing indicator. `shoot_date` on the day screen hit
   both: handled by allowing a bounded number of same-element repeats for
   `date`/`time`/`datetime-local`/`month`/`week` inputs, and only requiring the
   visible-focus check the first time such a control gains focus, not on its own
   internal-segment repeats.

## Verified the test catches a real regression

Per the item's own failure-case discipline (FR-63/82's precedent): temporarily changed
`.lang-toggle:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }` to
`outline: none` in `frontend/src/styles.css`, rebuilt, and re-ran
`test_crew_sheet_demo_keyboard_nav` — it failed loudly and specifically
(`BUTTON#langToggle 'English' has no visible focus indicator (Tab #1)`). Reverted the
change, rebuilt, and confirmed the full suite green again before committing.

## Verification

`frontend/tests/test_keyboard_nav.py`: 3 passed (parametrized ×2 for locale on the
demo crew sheet, ×1 for the combined Crew-tab/day-screen/personal-link flow). Full
frontend E2E suite: 93 passed, 3 skipped (same pre-existing skips as every prior
shift), no new failures. Backend suite: 327 passed, 3 skipped. `npm run
typecheck` and `vitest run` (66/66) clean. No backend/frontend product code changed —
only the new test file — so no deploy is needed.

## Follow-up pass (FR-186, 2026-10-19): Cast, Locations, Members, Settings tabs

FR-183 found the same four editor tabs — Cast, Locations, Members, Settings — had
never had an axe-core pass; this item is the keyboard-nav equivalent of that gap, not
covered by the four screens above. Added
`test_cast_locations_members_settings_tabs_keyboard_nav` to
`frontend/tests/test_keyboard_nav.py`: after creating a production, each tab gets one
real row first (a cast member with a character name, a location with a name and
address, a viewer-role member) so `walk_keyboard()` exercises each tab's "Remove"/role
controls, not just its empty add-row fields, before Settings (no add-row of its own,
walked as-is).

**Zero keyboard-operability defects on any of the four tabs.** Same root cause as the
2026-10-05 pass: every interactive control under `frontend/src/editor` already carries
the shared `input:focus-visible, select:focus-visible, textarea:focus-visible` rule in
`editor.css`, and none of these four tabs opens an overlay or dialog that could hold
focus, so the dod's own keyboard-trap failure case had nothing to exercise today —
confirmed directly (grepped `frontend/src/editor` for `<dialog`/a focus-trapping
modal: none), not assumed from the 2026-10-05 finding.

**Failure-case discipline run and verified** (same precedent as the 2026-10-05 pass
and FR-63/82's axe-core version): temporarily added `#productionStatus:focus-visible {
outline: none; }` to `editor.css`, rebuilt, and re-ran the new test — failed loudly and
specifically (`SELECT#productionStatus 'prep\nshooting\nwrapped' has no visible focus
indicator (Tab #2)`), proving the test actually catches a real regression on this tab,
not just that it passes today. Reverted the change, rebuilt, and confirmed `git diff`
showed the CSS file byte-identical to before (no residual change shipped) before
re-running the full suite clean.

One incidental finding, not this item's scope: adding a location in this sandbox logs
`Geocoding failed for 'Trojská 1, Praha 7': 403 Forbidden` (the same Nominatim-egress
block FR-106/FR-19 already document) — harmless here since the test only asserts the
location's name appears in the list, not that it resolved, but noted so a future
reader isn't surprised by the warning in the test's own stderr capture.

### Verification (FR-186)

`frontend/tests/test_keyboard_nav.py`: 4 passed (the new test plus the three from the
2026-10-05 pass, unchanged). Full frontend E2E suite: 97 passed, 3 skipped (same
pre-existing skips), no new failures. Backend suite: 248 passed (unaffected — no
backend code touched). `npm run typecheck` clean; `vitest run` 71/71 clean. No
backend/frontend product code changed — only the new test and this doc — so no deploy
is needed.

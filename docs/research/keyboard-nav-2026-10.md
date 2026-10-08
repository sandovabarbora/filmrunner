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

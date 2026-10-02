# FR-123 — fresh end-to-end exploratory pass (2026-10-02, 10:00 shift)

Role: qa. Goal per the item: build the stack from scratch this shift (no
cached state) and walk the connect-first path as a real AD would, hunting
for product bugs rather than re-verifying desk research.

## What was built fresh this shift

- New local Postgres 16 role/db (`filmrunner`), neither existed this session.
- `alembic upgrade head` from empty — all 20 migrations applied cleanly.
- `python -m app.seed_demo` — seeded the demo production/call sheet.
- `npm install` + `npm run build` from scratch (neither `node_modules/` nor
  `dist/` existed this session) — clean build, no warnings.
- Backend served on a real `uvicorn`, frontend `dist/` served on a real
  `vite preview` — the same artifacts a deploy would ship, not the dev server.

## The walkthrough

Drove the built app with a real headless Chromium (Playwright, iPhone-width
viewport) as a human AD would, connecting with the local dev bearer token the
way README's own quick-start describes (no sign-in UI, same as the existing
E2E suite's own `_connect` helper — this build has no Supabase configured
locally, so the magic-link flow isn't reachable in this sandbox either way):

1. Created a new production ("Explore …").
2. Added one crew member by hand (HoD), then imported the other 11 from
   `tests/fixtures/crew-12.xlsx` — the import preview correctly flagged the
   already-added duplicate, a bad phone number ("ask Klára" — not a number,
   left out with a stated reason), and a row with no position (defaulted to
   "Crew" with a stated reason). Final crew count: 12, confirmed in the DB.
3. Added one cast member (character, pickup time).
4. Created Day 1, added a scene, published REV A.
5. Opened a crew member's personal link — correctly shows their own call
   first, their department, "Who to call" collapsed for other departments.
6. Opened the plain (non-personal) viewer link — correctly shows the full
   "Who to call" list (6 HoDs) instead of one person's own call, the
   connect-first difference between the two link types working as designed.
7. Opened the PDF link (`?print=1`) — `window.print()` fires on load as
   designed (confirmed via a stubbed `window.print`, the same technique
   `test_pdf_e2e.py` uses since headless Chromium has no real print dialog).
8. Checked a WhatsApp nudge link — `wa.me/<number>?text=...` carries the
   correct REV letter, day number and crew call.
9. Checked the browser console throughout (errors + warnings + page errors
   captured) — none.

Screenshots of every step are in this shift's own working session, not
committed (they're a one-off verification artifact, not something a future
shift needs to re-read).

## One thing investigated and ruled out as not a bug

The "Actual times" panel on a brand-new, just-published day showed
`19:40` in all four time fields and a rain-related sentence in the note
field, which looked at first glance like leaked data from another
production. Checked two ways before concluding anything: queried the new
call sheet's row directly in Postgres (`actual_first_shot` /
`actual_lunch_out` / `actual_lunch_in` / `actual_wrap` / `actual_note` were
all `NULL`), then read `frontend/src/editor/screens/DayEditor.tsx:559-569`
— `19:40` and the rain sentence are the fields' `placeholder` text (example
copy), not stored values; `value={actuals[key] ?? ""}` is genuinely empty.
Not a bug, not filed.

## Regression pass: the existing automated suites, run fresh

- Backend: `pytest` — **153/153 passed** (real Postgres, full Alembic chain,
  not `create_all`).
- Frontend unit: `npm run typecheck` clean; `vitest run` — **53/53 passed**.
- Frontend E2E (Playwright, real built `dist/`, real backend, real
  Postgres) — **75/77 passed**. The 2 failures are both
  `test_locations_e2e.py` tests hitting the real Nominatim geocoding API,
  which this sandbox's egress proxy returns `403 Forbidden` for
  (`WARNING app.services.geocoding: Geocoding failed for 'Staroměstské
  náměstí, Praha 1': 403 Forbidden`) — the exact gap FR-106 (PR #265,
  still open) already exists to close by mocking Nominatim in these tests.
  Not a new finding; re-confirms the open PR is still needed.
  (Running this suite needed the same temporary Chromium-executable-path
  override prior shifts have documented for FR-107/PR #267 — applied,
  verified, and reverted before any commit, not part of this PR's diff.)

## Result

No new product defect found this shift. The connect-first path (production
→ crew import → cast → day → publish → personal link → plain link → PDF →
WhatsApp) works end to end on a freshly built, freshly seeded stack. The
only two non-green signals encountered were both already-tracked,
already-has-an-open-PR gaps (FR-106 Nominatim mock, FR-107 Chromium
revision), not new issues — per the item's own failure case, nothing here
is filed as a new backlog item since nothing reproduced as a real defect.

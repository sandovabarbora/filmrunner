# Status

Updated: 2026-09-21 14:00 (14:00 shift)

## today

Updated: 2026-09-21 14:00 (founder's interactive session, closing for now)

Hackathon week goal (founder, 2026-09-21): pilot-ready by Friday. A Prague AD can run a real shoot day end to end: sign in with a code, crew with photos, day with locations, publish, crew gets a push, personal links, PDF; and a landing page from the FR-6 positioning. Shifts hourly 09 to 17, everything auto-merges (TEAM.md).

- 11:00 — done: FR-22 (call sheet role/tooling desk research).
- 12:00 — done: FR-20 (Prague market sizing, BRIEF Q5). Between 11:00 and 12:00, other sessions (not this routine) merged FR-23, FR-24, FR-27, FR-29, FR-30, FR-31 to `main` — all now `done` in the backlog; `gh pr list --state open` was empty at the start of this shift, so nothing was skipped.
- 13:00 — done: FR-25 (landing page from the FR-6 positioning), PR #111 (`feat/fr-25-landing-page`), auto-merge enabled. `gh pr list --state open` was empty at the start of this shift (PR #102 had already merged). Between 12:00 and this shift, another session (not this routine) merged FR-36 (who has opened REV B) to `main`.
- 14:00 — nothing is `ready`+`gated:no` any more (FR-25 was the last one). Two candidates, check their current state first: (a) **FR-17** (connected app) is `in-progress`, `gated: no`, but carries no note at all — given how much has shipped since it was opened (FR-27 locations tab, FR-30 day navigation, FR-31 crew paste, FR-32 stable per-person links, FR-36 seen-by), its dod may already be substantially met; verify against the live dod bullets and either close it with a note or name the actual remaining ungated slice. (b) if FR-17 turns out to still have real ungated work, that is plannable per TEAM.md 6b. Failing both, the shift acts as pm and proposes one new backlog item per TEAM.md §7.
- 14:00 (this routine shift) — after the founder's own 09:00–14:00 interactive session closed (seventeen items merged, see below), the afternoon backlog was already refilled with four fresh `ready`+`gated:no` items: FR-38, FR-39, FR-40, FR-41 (see "Afternoon shifts" below). `gh pr list --state open` was empty at shift start, so nothing was skipped; FR-17 was left as the founder's session flagged it (no time to also re-verify its dod this shift, and it wasn't the top-priority ready item). Took the highest-priority ready item, **FR-38** (delete a location): delivered `DELETE /productions/{id}/locations/{id}` (CREW_EDIT) — nulls `location_id` on every schedule item across any revision that pointed to the location before deleting the row, so a published day never breaks; a Remove button on the Locations tab with the same one-step `window.confirm` pattern Crew's remove uses. Handled the dod's failure case directly: once a day's only location is deleted, the FR-27 sunrise hint reappears with its no-location copy (verified live, not just read from the code — see tests below), never a blank sunrise field with no explanation. PR #122 (`fix/fr-38-delete-a-location`), auto-merge enabled — touches `backend/` and `frontend/`, allowed under hackathon mode. FR-38 set to `done`.
- Later shifts: FR-8/FR-16's live-Fly-URL verification (repeat attempts, blocked by this session's egress proxy every time so far), the iOS manual test protocol executed as far as possible headless, photo flow behind INBOX #4.
- Founder's session, 09:00–14:00: **seventeen items merged and live** — FR-24 personal calls per day, FR-29 WhatsApp share (+ cast lines), FR-23 "REV B replaces A" + what changed, FR-27 location hint + sunrise auto-fill, FR-30 next day from this one, FR-31 paste the crew list, FR-32 one link per person for the whole shoot, FR-33 cast, FR-34 cancel a day / rename or wrap a production, FR-35 Where block, FR-36 who opened REV B + nudge, FR-37 send everyone their link, FR-42 tomorrow at a glance, FR-43 days list at a glance, FR-44 personal-calls picker; demo sheet complete; landing screenshots retaken with real fonts. Fly deployed seven times (migrations up to e2a7c5d9f4b6); Pages at fbc13a8. Backend 116 tests, frontend 26 unit + 44 E2E, all green; live run on the deployed stack 27/27 twice (`docs/research/pilot-readiness-live3.py`).
- **Founder-only blocker for a functional app: INBOX #3 (SMTP for the sign-in e-mail)** — exact click path now in the INBOX entry (Gmail App Password, 5 minutes). Then the phone protocol, steps 1–9 in the readiness file.
- Afternoon shifts: FR-38 delete a location (**done this shift**, PR #122), FR-39 weather on publish, FR-40 readiness re-run (build on the live3 run), FR-41 outreach message — next up, in that order. **Backend PRs from shifts need `cd backend && fly deploy` from the founder's Mac or the founder's next session** (no deploy token in GitHub by decision, so PR #122 also needs a deploy once merged — no migration, just new code).

## pm
- summary: unchanged this shift (this shift's own item was engineering, FR-38 — see below). FR-1/FR-2/FR-3/FR-21/FR-22 all still `done`.
- tests: n/a (no pm item this shift)
- blockers: `WebFetch` remains blocked by this session's egress proxy — confirmed again by prior shifts; `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine).

## engineering (tech-lead + frontend)
- summary: this shift delivered FR-38 (delete a location): `DELETE /productions/{id}/locations/{id}` in `backend/app/routers/productions.py` nulls `location_id` on any `ScheduleItem` (past or current revision) referencing the location before deleting it — otherwise the plain FK constraint (no `ondelete`) would reject the delete outright once a scene had used it. Frontend: `api.deleteLocation`, a Remove button on the Locations tab (`frontend/src/editor/screens/Production.tsx`) matching Crew's one-step confirm. PR #122 (`fix/fr-38-delete-a-location`), auto-merge enabled. FR-17 (connected app) stays `in-progress` with no note naming a remaining ungated slice, as the 13:00 shift flagged — not re-checked this shift; a future shift should verify its dod against what FR-27/FR-30/FR-31/FR-32/FR-36 have since delivered before treating it as workable. FR-8/FR-16 stay `in-progress`, both gated on the founder, remaining verification blocked by egress.
- tests: this shift's own change — backend 118/118 (2 new: delete drops the link and the day still publishes with a further revision; delete of a nonexistent location 404s). Frontend: `npm run typecheck`/`npm run build` clean, `npm test` 26/26, full Playwright suite 45/47 (2 pre-existing, unrelated `test_locations_e2e.py` Nominatim-egress failures — same gap every prior shift touching that suite has hit; one of the two, `test_tomorrow_at_a_glance_on_a_personal_link`, is flaky only under full-suite contention, confirmed to pass standing alone). New E2E test (`test_deleting_a_location_drops_it_from_a_published_scene_without_breaking_the_day`) exercises the dod's own failure case for real: publish a day with a located scene, delete the location from the Locations tab, reopen the day, and confirm both the location select and the FR-27 sunrise hint reset — against a real build and a real uvicorn+Postgres API (this sandbox's pinned Chromium revision absent as prior shifts noted; verified via a temporary `conftest.py` browser-executable override, reverted before commit, not part of the diff).
- blockers: FR-8/FR-16's live-Fly-URL verification remains blocked by this session's egress proxy; no `fly` CLI installed either. PR #122 needs `cd backend && fly deploy` once merged (no migration).
- needs_approval: no new items this shift.

## security (gate)
- summary: unchanged this shift; FR-7 stands `done` (re-verified 2026-09-16 17:00, 88/88 backend tests). FR-5 (the gate checklist itself) stands `done`, merged. FR-38's new endpoint is behind the existing `CREW_EDIT` permission dependency, same as every other location-mutating route; no new auth surface introduced.
- tests: n/a — no security-specific work this shift.
- blockers: none.
- needs_approval: no.

## marketing
- summary: unchanged this shift (this shift's own item was engineering, FR-38). FR-6/FR-20/FR-25 all still `done`. FR-41 (pilot outreach message) is next up in the afternoon queue.
- tests: n/a
- blockers: none this shift.
- needs_approval: no

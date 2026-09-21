# Status

Updated: 2026-09-21 13:00 (13:00 shift)

## today

Updated: 2026-09-21 13:30 (founder's interactive session, after the 13:00 shift)

Hackathon week goal (founder, 2026-09-21): pilot-ready by Friday. A Prague AD can run a real shoot day end to end: sign in with a code, crew with photos, day with locations, publish, crew gets a push, personal links, PDF; and a landing page from the FR-6 positioning. Shifts hourly 09 to 17, everything auto-merges (TEAM.md).

- 11:00 — done: FR-22 (call sheet role/tooling desk research).
- 12:00 — done: FR-20 (Prague market sizing, BRIEF Q5). Between 11:00 and 12:00, other sessions (not this routine) merged FR-23, FR-24, FR-27, FR-29, FR-30, FR-31 to `main` — all now `done` in the backlog; `gh pr list --state open` was empty at the start of this shift, so nothing was skipped.
- 13:00 — done: FR-25 (landing page from the FR-6 positioning), PR #111 (`feat/fr-25-landing-page`), auto-merge enabled. `gh pr list --state open` was empty at the start of this shift (PR #102 had already merged). Between 12:00 and this shift, another session (not this routine) merged FR-36 (who has opened REV B) to `main`.
- 14:00 — nothing is `ready`+`gated:no` any more (FR-25 was the last one). Two candidates, check their current state first: (a) **FR-17** (connected app) is `in-progress`, `gated: no`, but carries no note at all — given how much has shipped since it was opened (FR-27 locations tab, FR-30 day navigation, FR-31 crew paste, FR-32 stable per-person links, FR-36 seen-by), its dod may already be substantially met; verify against the live dod bullets and either close it with a note or name the actual remaining ungated slice. (b) if FR-17 turns out to still have real ungated work, that is plannable per TEAM.md 6b. Failing both, the shift acts as pm and proposes one new backlog item per TEAM.md §7.
- Later shifts: FR-8/FR-16's live-Fly-URL verification (repeat attempts, blocked by this session's egress proxy every time so far), the iOS manual test protocol executed as far as possible headless, photo flow behind INBOX #4.
- Founder's session, 09:00–13:30: **thirteen items merged and live** — FR-24 personal calls per day, FR-29 WhatsApp share, FR-23 "REV B replaces A" + what changed, FR-27 location hint + sunrise auto-fill, FR-30 next day from this one, FR-31 paste the crew list, FR-32 one link per person for the whole shoot, FR-33 cast, FR-34 cancel a day / rename or wrap a production, FR-35 Where block on the sheet, FR-36 who opened REV B + nudge, FR-37 send everyone their link, demo sheet complete, landing screenshots retaken with real fonts. Fly deployed five times (migrations up to e2a7c5d9f4b6). Backend 114 tests, frontend 25 unit + 43 E2E, all green.
- **Founder-only blocker for a functional app: INBOX #3 (SMTP for the sign-in e-mail).** Without it nobody new can sign in. Gmail App Password into Supabase Auth → SMTP settings, or a Resend account. Then the iPhone protocol (FR-28): install, offline honesty, push, WhatsApp share, one link per person.
- Founder's session, next: a live run-through on the deployed app with the founder's own production once SMTP is in; until then small completions (delete a location, weather auto-fill on publish) and whatever the phone protocol turns up.

## pm
- summary: unchanged this shift (this shift's own item was marketing, FR-25 — see below). FR-1/FR-2/FR-3/FR-21/FR-22 all still `done`.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy — confirmed again this shift (every vendor and Czech-industry domain tried by prior shifts); `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine).

## engineering (tech-lead + frontend)
- summary: this shift's own item (FR-25) touched `frontend/` only (a new landing entry, no shared component behaviour changed except one added link on the root entry page); nothing else in engineering changed. Since the 12:00 shift's STATUS update, another session (not this routine) merged FR-36 (seen-by + WhatsApp nudge) to `main`, now `done`. FR-17 (connected app) stays `in-progress`, still with no note naming a remaining ungated slice despite substantial related work landing since (FR-27, FR-30, FR-31, FR-32, FR-36) — flagged above under "14:00" for the next shift to check against its actual dod before treating it as workable. FR-8/FR-16 stay `in-progress`, both gated on the founder, remaining verification blocked by egress.
- tests: this shift's own change verified — `npm run typecheck`/`npm run build` clean, `npm test` 23/23, full Playwright suite 39/41 (2 pre-existing, unrelated `test_locations_e2e.py` Nominatim-egress failures, same gap every prior shift touching that suite has hit).
- blockers: FR-8/FR-16's live-Fly-URL verification remains blocked by this session's egress proxy; no `fly` CLI installed either.
- needs_approval: no new items this shift.

## security (gate)
- summary: unchanged this shift; FR-7 stands `done` (re-verified 2026-09-16 17:00, 88/88 backend tests). FR-5 (the gate checklist itself) stands `done`, merged.
- tests: n/a — no backend code touched this shift.
- blockers: none.
- needs_approval: no.

## marketing
- summary: 13:00 shift delivered FR-25 (landing page from the FR-6 positioning): `frontend/landing.html`, a third Vite entry carrying FR-6's chosen position ("live and offline-honest"), three real screenshots of the bundled demo call sheet taken by a committed Playwright script (`frontend/scripts/take_landing_screenshots.py`), a live-demo link, proof points and who-it's-for from `positioning.md`, and a no-forms "Request a pilot" mailto to the founder. Czech/English toggle (two static blocks, no framework, defaults to browser language, falls back to Czech with no JS). Root entry page links to it. Handled the dod's failure case: a screenshot the script can't produce is simply not written, and the page removes any `<figure>` whose image 404s rather than showing it broken. PR #111 (`feat/fr-25-landing-page`), auto-merge enabled — touches `frontend/`, allowed under hackathon mode (only `TEAM.md` itself is excluded). FR-25 set to `done`; FR-6/FR-20 unchanged, still `done`.
- tests: n/a for the copy itself; the entry's code verified as above (typecheck/build/unit/E2E).
- blockers: none this shift — this item didn't need `WebFetch`/`WebSearch`.
- needs_approval: no

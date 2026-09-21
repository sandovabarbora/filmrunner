# Status

Updated: 2026-09-21 09:00 (09:00 shift)

## today

Hackathon week goal (founder, 2026-09-21): pilot-ready by Friday. A Prague AD can run a real shoot day end to end: sign in with a code, crew with photos, day with locations, publish, crew gets a push, personal links, PDF; and a landing page from the FR-6 positioning. Shifts hourly 09 to 17, everything auto-merges (TEAM.md).

- 11:00 — FR-22 (if ready) or the highest ready item; then FR-20.
- Later shifts: items proposed by the 11:00 shift and the brief toward the goal above: "REV B replaces A" note on the sheet (FR-11 leftover), per-day personal call overrides, locations tab polish (FR-19 follow-ups), iOS manual test protocol executed as far as possible headless, landing page (docs/marketing/positioning.md → frontend/landing.html), photo flow behind INBOX #4.


## pm
- summary: unchanged this shift (this shift's own item was marketing, FR-6). FR-1's brief correction, FR-3's discovery plan, FR-2's teardown, and FR-21's switching-cost teardown all stand `done`. PR #81 (FR-1) merged to `main` by the founder overnight — no longer awaiting anything.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for most external domains; `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine).

## engineering (tech-lead + frontend)
- summary: unchanged this shift (this shift's own item was marketing, FR-6). PRs #79 (FR-18) and #83 (FR-4) both merged to `main` by the founder overnight — FR-18 stays `in-progress` (its photo bullet remains gated on INBOX #4), FR-4 stands `done`, neither is awaiting a merge any longer. FR-8's iOS-Safari-over-real-URL verification task attempted again this shift (09:00) and confirmed still undoable: `filmrunner-api.fly.dev` and `api.fly.io` both reject the CONNECT tunnel with 403 through this session's egress proxy, the same block every prior attempt since 2026-09-14 has hit. FR-8 stays `in-progress`, unchanged. FR-16's live-verification task (same blocked host) was not separately re-run this shift since the block was just confirmed on the identical domain; also treated as skipped. FR-16 stays `in-progress`, unchanged.
- tests: n/a — no code touched this shift.
- blockers: FR-8/FR-16's live-Fly-URL verification remains blocked by this session's egress proxy (confirmed again 2026-09-21 09:00); no `fly` CLI installed either, so there is no way to reach the deployed API from here. Carried over: FR-18's photo upload gated on INBOX #4.
- needs_approval: yes — INBOX #4 (Supabase Storage bucket/secret for FR-18's photo upload), needing the founder's own credentials.

## security (gate)
- summary: unchanged this shift; FR-7 stands `done` (re-verified 2026-09-16 17:00, 88/88 backend tests). FR-5 (the gate checklist itself) stands `done`, merged.
- tests: n/a — no code touched this shift.
- blockers: none.
- needs_approval: no.

## marketing
- summary: 09:00 shift delivered FR-6 (positioning draft): `docs/marketing/positioning.md`, four alternatives considered and one chosen (live+offline-honest), grounded in FR-1's brief and FR-2's teardown, with the dod's competitor-ownership failure case addressed explicitly against StudioBinder's own "living call sheet" claim. PR #86 (`docs/fr-6-positioning-draft`), auto-merge enabled (docs-only). FR-6 set to `done`.
- tests: n/a (docs-only)
- blockers: none
- needs_approval: no

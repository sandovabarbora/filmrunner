# Status

Updated: 2026-09-21 11:00 (11:00 shift)

## today

Hackathon week goal (founder, 2026-09-21): pilot-ready by Friday. A Prague AD can run a real shoot day end to end: sign in with a code, crew with photos, day with locations, publish, crew gets a push, personal links, PDF; and a landing page from the FR-6 positioning. Shifts hourly 09 to 17, everything auto-merges (TEAM.md).

- 11:00 — done: FR-22 (call sheet role/tooling desk research). FR-24 (per-day personal calls) has an open PR (#93, from an interactive session, `mergeable_state: blocked`, no CI status yet) so per the shift contract it was not picked up, even though it's still `state: ready` in the backlog.
- 13:00 — FR-20 (Prague market sizing) is next: highest `ready`+`gated:no` item left once FR-24's PR is excluded. Re-check `gh pr list` first in case #93 merged or closed.
- Later shifts: items proposed by the 11:00 shift and the brief toward the goal above: "REV B replaces A" note on the sheet (FR-11 leftover), per-day personal call overrides (in progress via PR #93), locations tab polish (FR-19 follow-ups), iOS manual test protocol executed as far as possible headless, landing page (docs/marketing/positioning.md → frontend/landing.html), photo flow behind INBOX #4.


## pm
- summary: 11:00 shift delivered FR-22 (desk-research proxy for BRIEF Q1/Q2): `docs/research/call-sheet-role-and-tooling-signals.md`. `WebFetch` confirmed egress-blocked this shift for every domain tried, Czech and international alike (csfc.cz, biofilms.cz, nsp.cz), not just vendor domains as FR-2/FR-21 found — built from `WebSearch` snippets instead, all cited. Strongest finding: a real, named Prague production coordinator's LinkedIn profile (credited on Stillking Films-scale productions) lists call sheets as an explicit skill — one genuine Czech-market confirmation of Q1. No Czech-specific tool name surfaced for Q2 despite four targeted searches; marked unverified per the dod's failure case. PR #94 (`docs/fr-22-call-sheet-role-tooling-signals`), auto-merge enabled (docs-only). FR-22 set to `done`. FR-1/FR-3/FR-2/FR-21 unchanged, all still `done`.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy — now confirmed for ordinary industry/job-classification sites too, not just vendor domains; `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine).

## engineering (tech-lead + frontend)
- summary: unchanged this shift (this shift's own item was pm, FR-22). PRs #79 (FR-18) and #83 (FR-4) both merged to `main` by the founder overnight — FR-18 stays `in-progress` (its photo bullet remains gated on INBOX #4), FR-4 stands `done`. New this shift: PR #93 (`feat/fr-24-personal-calls`, FR-24, from an interactive session, not the routine) is open against `main`, `mergeable_state: blocked`, no CI status yet — noted so no shift picks up FR-24 while it's open (shift contract: never start an item whose dod depends on a still-open PR). FR-8/FR-16's live-Fly-URL verification was not re-attempted this shift (09:00 already confirmed the block this morning); unchanged, still `in-progress`.
- tests: n/a — no code touched this shift.
- blockers: FR-8/FR-16's live-Fly-URL verification remains blocked by this session's egress proxy (confirmed 2026-09-21 09:00); no `fly` CLI installed either. Carried over: FR-18's photo upload gated on INBOX #4. New: FR-24 blocked from pickup by open PR #93 until it merges or closes.
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

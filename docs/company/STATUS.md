# Status

Updated: 2026-09-21 12:00 (12:00 shift)

## today

Hackathon week goal (founder, 2026-09-21): pilot-ready by Friday. A Prague AD can run a real shoot day end to end: sign in with a code, crew with photos, day with locations, publish, crew gets a push, personal links, PDF; and a landing page from the FR-6 positioning. Shifts hourly 09 to 17, everything auto-merges (TEAM.md).

- 11:00 — done: FR-22 (call sheet role/tooling desk research).
- 12:00 — done: FR-20 (Prague market sizing, BRIEF Q5). Between 11:00 and 12:00, other sessions (not this routine) merged FR-23, FR-24, FR-27, FR-29, FR-30, FR-31 to `main` — all now `done` in the backlog; `gh pr list --state open` was empty at the start of this shift, so nothing was skipped.
- 13:00 — next up: FR-25 (landing page from the FR-6 positioning), the highest remaining `ready`+`gated:no` item. Re-check `gh pr list --state open` first in case this shift's own PR #102 (FR-20) is still pending its CI/auto-merge.
- Later shifts: FR-8/FR-16's live-Fly-URL verification (repeat attempts, blocked by this session's egress proxy every time so far), the iOS manual test protocol executed as far as possible headless, photo flow behind INBOX #4, FR-17's connected-app remaining work (no note yet names an ungated remaining slice — check before picking up).


## pm
- summary: unchanged this shift (this shift's own item was marketing, FR-20 — see below). FR-1/FR-2/FR-3/FR-21/FR-22 all still `done`.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy — confirmed again this shift for the Czech Film Commission's statistics page and, newly, for `en.wikipedia.org` (no prior shift had tried Wikipedia); `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine).

## engineering (tech-lead + frontend)
- summary: unchanged this shift (this shift's own item was marketing, FR-20). Since the 11:00 shift's STATUS update, other sessions (not this routine) merged six PRs to `main`: FR-23 (revision diff), FR-24 (per-day personal calls, formerly PR #93), FR-27 (location hint), FR-29 (WhatsApp share), FR-30 (next-day-from-this), FR-31 (paste crew list) — all now `done`. FR-17 (connected app) stays `in-progress` with no note yet naming a remaining ungated slice; FR-8/FR-16 stay `in-progress`, both gated on the founder (INBOX #2/#5 already done, remaining verification blocked by egress).
- tests: n/a — no code touched this shift.
- blockers: FR-8/FR-16's live-Fly-URL verification remains blocked by this session's egress proxy; no `fly` CLI installed either. Carried over: FR-18's photo upload gated on INBOX #4 (resolved as "not needed" — photos now stored in Postgres, per FR-18's own note).
- needs_approval: no new items this shift.

## security (gate)
- summary: unchanged this shift; FR-7 stands `done` (re-verified 2026-09-16 17:00, 88/88 backend tests). FR-5 (the gate checklist itself) stands `done`, merged.
- tests: n/a — no code touched this shift.
- blockers: none.
- needs_approval: no.

## marketing
- summary: 12:00 shift delivered FR-20 (Prague market sizing, BRIEF Q5): `docs/research/prague-market-sizing.md`. No public source publishes a 30-day active-production count, so the doc builds an explicit order-of-magnitude estimate from five dated proxies (2025 Czech film premieres, 2025 incentive-application growth, named large productions currently shooting, a productionlist.com Prague count of unverified date range, FAMU's unquantified-per-year but real annual output), each flagged for what it does and does not measure, then compares that estimate against a word-of-mouth critical-mass threshold (Rogers' diffusion research, ~15-20% of an audience) applied to the addressable audience of call-sheet-assemblers rather than the general public. Handled the dod's failure case: since no source gives a precise count, proposed one estimation question for FR-3's interview script instead of guessing a number. PR #102 (`docs/fr-20-prague-market-sizing`), auto-merge enabled (docs-only). FR-20 set to `done`. FR-6 unchanged, still `done`.
- tests: n/a (docs-only)
- blockers: `WebFetch` blocked for every domain tried this shift (Czech Film Commission statistics page, `productionlist.com`, `filmcenter.gov.cz`'s 2024 review, `en.wikipedia.org`); built entirely from `WebSearch` snippets, all cited with date checked.
- needs_approval: no

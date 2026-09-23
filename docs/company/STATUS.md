# Status

Updated: 2026-09-23 10:00 (10:00 shift)

## today

Updated: 2026-09-23 08:00 (morning brief)

Hackathon week goal (founder, 2026-09-21): pilot-ready by Friday. A Prague AD can run a real shoot day end to end: sign in with a code, crew with photos, day with locations, publish, crew gets a push, personal links, PDF; and a landing page from the FR-6 positioning. Shifts hourly 09 to 17, everything with green `ci` auto-merges (TEAM.md hackathon mode, through 2026-09-25).

The `ready`+`gated:no/partial` queue held exactly one item (FR-68) at plan time, so this brief refilled the backlog first: PR #172 (`docs/backlog-proposals-2026-09-23`, auto-merge enabled) proposes FR-69 through FR-76, each citing a concrete, already-named gap (an open code TODO, a dropped dod bullet from a `done` item, an ADR's own unaddressed revisit trigger, or a doc left stale after its blocking dependency shipped) — verified by reading the cited file/line before writing each item. Plan below assumes PR #172 merges before or during the 09:00 shift, the same pattern prior pm-fallback proposals have followed all week; if a slot's item is still unmerged when that shift runs, fall through to the next merged item and note it.

Plan (priority order = file order in BACKLOG.md):
- 09:00 — FR-68 (qa): live write-path check script + guarded CI step for the five features never exercised against the deployed API (delete a location, weather-on-publish, tomorrow-at-a-glance, days-list-at-a-glance, personal-calls picker); files the token/account as a new INBOX item, ships ungated.
- 10:00 — FR-69 (tech-lead): DB-level partial unique index so only one call-sheet revision can ever be "current", closing the TODO left in `call_sheet.py` since Postgres became the production DB. Done this shift: PR #176, merged.
- 11:00 — FR-70 (marketing): rewrite positioning.md's "Local" rejection, which still reads as if FR-20 (Prague market sizing) never ran.
- 12:00 — FR-71 (qa): run Lighthouse mobile performance against the FR-52 pilot-scale sheet — the one dod bullet FR-52 shipped without.
- 13:00 — FR-72 (tech-lead): measure publish latency with 40-60 real push subscriptions, closing ADR-007's own named revisit trigger.
- 14:00 — FR-73 (qa): 200% zoom/reflow check on the crew sheet and personal link, the one a11y dimension FR-63 explicitly left unmeasured.
- 15:00 — FR-74 (pm): a data-retention policy doc plus a read-only dry-run report, closing the gap FR-59 flagged but didn't fill.
- 16:00 — FR-75 (frontend): make the weather-suggestion failure message tell "too far ahead to forecast" apart from "provider down".
- 17:00 — FR-76 (qa): pin today's 60-scene/day schedule size as a CI regression ceiling; always sends the day summary regardless of what else happened.

Not scheduled today: FR-28 stays correctly `blocked` on the founder's own phone/SMTP steps (INBOX #3). If a shift finds the queue already re-thinned by a parallel (non-routine) session, it acts as pm per TEAM.md §7 rather than sitting idle.

### Yesterday (2026-09-22), for reference

Full detail in `LOG.md`; condensed here to keep this file readable. Nine shifts ran: 09:00 FR-46 (copy crew from another production, PR #140), 10:00 FR-47 (PDF of the day, PR #142), 11:00 FR-49 (contact actions — WhatsApp/copy, PR #148), 12:00 FR-50 (publish history panel, PR #156), 13:00 FR-54 (landing flow recording, PR #158, after finding FR-51/52/53 already merged by a parallel founder session), 14:00 found the queue emptied by a parallel session and proposed FR-66 (live-stack CI check, PR #163), 15:00 proposed FR-67 (astronomy accuracy vs. a live reference, PR #166 → delivered by 16:00's own shift, PR #168, 8/8 checks pass), 17:00 proposed FR-68 (this brief's carry-over item). A large parallel (non-routine, likely the founder's own) session separately merged FR-48, FR-51, FR-52, FR-53, FR-58, FR-59, FR-60, FR-61, FR-62, FR-63, FR-64, FR-65 and closed FR-8/FR-16/FR-17 as done. End of day: every backlog item `done` except FR-28 (`blocked`) and FR-68 (`ready`, carried into today's plan).

**Founder-only blocker for a functional app, unchanged**: INBOX #3 (custom SMTP for the sign-in e-mail — exact click path already in the item, ~5 minutes with a Gmail App Password). Then the real-iPhone protocol (FR-28) can finally run.

## pm
- summary: carried over from 2026-09-22 17:00 — FR-1/FR-2/FR-3/FR-6/FR-20/FR-21/FR-22/FR-41/FR-59/FR-64 all `done`. This brief (08:00, 2026-09-23) opened PR #172 refilling the backlog (FR-69–FR-76); FR-74 in today's plan is a pm item.
- tests: n/a.
- blockers: `WebFetch`/direct `curl` to external domains remains blocked by this session's egress proxy; `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates, founder's own network) and INBOX #3 (custom SMTP for sign-in, the founder-only blocker for any new person signing in) both still `pending`.

## engineering (tech-lead + frontend + qa)
- summary: 09:00 shift (qa) took FR-68 per today's plan: `scripts/check_live_write_path.py` (PR #174, branch `test/fr-68-live-write-path-check`) drives the live API through five features never exercised there — FR-38 (delete a location), FR-39 (weather auto-fill), FR-42 (tomorrow at a glance), FR-43 (days list at a glance), FR-44 (personal calls picker) — by creating a disposable `CI check <uuid>` production and publishing three real revisions. Wired into `pilot-readiness.yml` guarded on `FILMRUNNER_CI_TOKEN`, skipped (not failed) until the token exists or if it's ever rejected. FR-68 set to `done` (ungated dod delivered); gated half (the token itself) filed as INBOX #6. Doc-only + `scripts/`/`.github/workflows/` — auto-merge enabled per hackathon mode. 10:00 shift (tech-lead) took FR-69: a partial unique index `uq_call_sheet_revisions_one_current` on `call_sheet_revisions(call_sheet_id) WHERE is_current` (migration `22f098e3dc1d`), also added to the SQLAlchemy model's `__table_args__` so the test suite's own `create_all`-based schema enforces it too, closing the TODO at `call_sheet.py:94`. PR #176 (`feat/fr-69-current-revision-unique-index`), auto-merged (`ci` green). Backend changed: deploy needed (migration only, no data change). FR-69 set to `done`. Remaining today's-plan items (FR-70 through FR-76) are for the next shifts.
- tests: FR-68's script verified against a real local Postgres + uvicorn (this sandbox's egress proxy blocks the live host, same limitation FR-66 worked around): 10/11 checks pass; the one local failure (FR-39 weather auto-fill) is the same known egress block hitting Open-Meteo, falling back to blank exactly as designed — not a script bug, expected to pass live. Also verified the script's own skip paths: a rejected token reports "skipped" (exit 0), a missing token exits 1 with a clear message (never reached in CI, guarded by the workflow `if:`). FR-69 verified against a real local Postgres: full backend suite 144/144 pass (1 new test); ran `alembic upgrade head` from scratch on a fresh DB (clean chain); the dod's own failure case exercised for real — seeded two current revisions for one call sheet, then applied the new migration alone, which raised a Postgres `UniqueViolation` naming the exact `call_sheet_id` in its `DETAIL` line rather than silently dropping a row.
- blockers: none open right now beyond the standing egress-proxy limits on this sandbox (does not block CI, which runs with open egress).
- needs_approval: yes — new INBOX #6 (GitHub Actions secret `FILMRUNNER_CI_TOKEN`, needed for the new guarded workflow step to actually run; the step reports "skipped" harmlessly until then).

## security (gate)
- summary: unchanged — FR-7 and FR-5 stand `done`, last re-verified 2026-09-16.
- tests: n/a this brief.
- blockers: none.
- needs_approval: no.

## marketing
- summary: unchanged from 2026-09-22 — FR-6/FR-20/FR-25/FR-41/FR-54 all `done`. Today's plan adds FR-70 (revisit the positioning doc's stale "Local" rejection). Sending FR-41's outreach drafts and FR-3's own invitation (INBOX #1) both still wait on the founder.
- tests: n/a.
- blockers: none.
- needs_approval: no new items this brief.

# Status

Updated: 2026-09-15 17:20 (17:00 shift)

## today

- 09:00 · FR-11 · frontend — done: QR code added to the editor's publish flow (PR #45, merged).
- 11:00 · FR-18 · frontend — done (code side): crew photo upload shipped (PR #48, merged); gated on INBOX #4 (Supabase Storage bucket + secret) before it works for real.
- 13:00 · FR-19 · tech-lead — done: geocoding, computed sunrise/sunset, a weather suggestion, and a nearest-hospital suggestion for locations, using keyless providers (PR #51, merged).
- 15:00 · FR-16 · frontend — done (code side): Web Push notifications on revision publish shipped (PR #53, merged); gated on INBOX #5 (VAPID keys as a Fly secret) before the "Enable notifications" control appears for real.
- 17:00 · FR-7 · security — done: re-verified all three founding-commit security fixes are actually in place (no new code needed) and flipped the backlog item's own state to done. See BACKLOG.md FR-7 note for detail.

Last scheduled shift of the day; day summary follows. Backlog refill not needed (FR-5 and FR-17/FR-18's remaining pieces still meet the ready+gated:no/partial floor).

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch`/`WebSearch` remain blocked by this session's egress proxy for most external domains (vendor pages, and confirmed earlier today for `timeanddate.com` and `api.sunrise-sunset.org`).
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: no new feature work this shift; it was FR-7's security-gate verification (see security below). Noted for the founder: PR #55 (`fix/alembic-merge-heads`, opened by an interactive session at 14:15, not this routine) fixes a real deploy blocker — the 13:00 (FR-19) and 15:00 (FR-16) shifts each added an Alembic migration from the same parent, so `alembic upgrade head` has two heads and would fail in the Fly release command. PR #55's CI is green and it is mergeable; it just awaits the founder's merge (this routine cannot merge a non-state PR without an approved INBOX item naming it). All four of today's feature PRs (#45, #48, #51, #53) are merged to main. Carried over: FR-18's photo upload gated on INBOX #4, FR-16's push gated on INBOX #5, both unchanged from earlier shifts' notes.
- tests: n/a this shift (no code changed by this routine); see security below for the verification run.
- blockers: PR #55 (migration-head fix) is unmerged, so `main`'s Alembic history still has two heads until the founder merges it — worth doing before the next deploy.
- needs_approval: yes — INBOX #5 (VAPID keypair) and INBOX #4 (Supabase Storage bucket/secret), both carried over, both needing the founder's own credentials.

## security (gate)
- summary: FR-7 re-verified this shift and flipped from `ready` to `done`. All three founding-commit findings hold: (1) `config.py` still refuses to boot with the default bearer token outside development; (2) the original innerHTML/XSS vector is now structurally impossible — the frontend fully migrated to React and `dangerouslySetInnerHTML` is used nowhere in `frontend/src`; the original regression test is still committed but was not re-run live this shift (would need a fresh build+browser cycle; the structural fix is stronger evidence than the original bug pattern could survive under); (3) `created_by`/`published_at` audit fields are confirmed server-set from the authenticated principal in both API entry points (`_audit_label` in `app/routers/call_sheets.py`), with the one body-value fallback inside the service layer reachable only from `seed_demo.py`'s own hardcoded call, not from any HTTP input. Ran the full backend suite against a freshly created local Postgres (container is ephemeral, so filmrunner/filmrunner_test roles and DBs were recreated this shift): 88/88 pass, including all spoofed-`created_by` and dev-token tests. FR-5 (the gate checklist itself) is still `ready`, not yet picked up — a future shift's task.
- tests: backend full suite 88/88 (fresh Postgres 16 this shift, no regressions since 2026-09-14's original fixes).
- blockers: none.
- needs_approval: no.

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

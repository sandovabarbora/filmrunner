# Status

Updated: 2026-09-18 13:00 (13:00 shift)

## today

**13:00 update**: took the plan's own item, **FR-18** (build the
offline-edit failure case for an *existing* crew member, frontend).
`Crew.save()`'s catch block used to fall through to the generic "No
connection, nothing was lost, try again" notice on a PATCH failure —
misleading, since nothing was actually kept. Added a small IndexedDB
queue (`frontend/src/editor/crewEdits.ts`, its own store, separate from
the day draft's `drafts.ts`) keyed by crew-member id: an offline edit now
saves there, the crew row shows the change immediately via an optimistic
overlay tagged "not saved", and the queue retries automatically the next
time the Crew tab loads (plus a manual "Sync" button per row). New
Playwright test; full `test_editor_e2e.py` (11/11) and the wider frontend
E2E suite (29/30 — one pre-existing, unrelated geocoding-test failure,
Nominatim blocked by this sandbox's egress proxy) verified against a real
build, a real API, and the pre-installed Chromium. `npm run typecheck`
and `npm run build` clean. PR #79 (`feat/fr-18-crew-offline-edit-queue`)
— touches `frontend/`, so per TEAM.md this needs the founder's own merge,
no auto-merge. FR-18 stays `in-progress` in BACKLOG.md: every ungated dod
bullet is now delivered, but the photo bullet itself remains gated on
INBOX #4 (Supabase Storage bucket + key), still `state: pending`.
`gh pr list --state open` was empty before this shift opened #79, so
nothing was skipped for depending on an open PR.

**11:00 update**: took the plan's own item, **FR-11** (verify/build the
crew-link failure case for a call sheet that no longer exists or isn't
public, frontend). `loader.ts` was collapsing a 404 from the public
call-sheet API into the same path as a network timeout, so the viewer
told the crew member to "get back in signal and reload" for a link that
can never load. Fixed: `loadCallSheet` now returns a distinct `not_found`
result on HTTP 404 (no cache fallback, same pattern `loadPersonal` already
used for an unknown personal token), and the UI shows "this call sheet
does not exist or is not available any more" instead. New Playwright test
added; full suite 13/13 passing against a real build. PR #77
(`fix/fr-11-not-found-failure-case`) — touches `frontend/`, so per TEAM.md
this needs the founder's own merge, no auto-merge. FR-11 set to `done` in
BACKLOG.md (all three dod bullets now hold). `gh pr list --state open`
was empty before this shift opened #77, so nothing was skipped for
depending on an open PR.

**09:00 update**: the FR-8 item below (iOS Safari over the real deployed
URL) could not be attempted this shift — `curl` to `filmrunner-api.fly.dev`
was rejected outright by this session's egress proxy ("organization
policy"), and there is no iOS device in this environment regardless (the
same gap FR-8's own notes have flagged since 2026-09-14). Skipping per the
shift contract; FR-8 stays `in-progress` with its note unchanged. Took the
next-highest-priority ready+ungated item instead: **FR-21** (switching-cost
teardown, pm), delivered in PR #75 (branch
`docs/fr-21-switching-cost-teardown`, auto-merge enabled, doc-only). FR-8
remains open for whichever future shift runs from an environment that can
reach the deployed API and has a real iOS device — neither is a routine
capability gap this shift can close by working harder.

The founder cleared the backlog overnight (2026-09-17, after the 17:00
shift): PRs #55, #58, #59, #66 and #72 all merged into `main` (confirmed
in `main`'s history), along with #48 and #51 from 2026-09-15 that had
also sat open. That ends the four idle days recorded 2026-09-15 to
2026-09-17 and unblocks real work again; `gh pr list --state open` is
now empty, so no item is skipped for depending on an open PR. `TEAM.md`
also picked up a 2026-09-17 rule auto-merging reversible docs-only PRs by
default, which should keep this from recurring for state/backlog PRs
specifically.

Five items qualify (`ready`, or `in-progress` with a note naming
remaining ungated work), taken in `BACKLOG.md` priority order:

- 09:00 · FR-8 — verify the PWA's service worker actually registers over
  the real deployed Fly-hosted HTTPS URL on iOS Safari (not just the
  GitHub Pages demo bundle), closing ADR-002's one unverified failure case.
- 11:00 · FR-11 — verify (and build if missing) the failure-case UI for a
  crew link to a call sheet that no longer exists or isn't public, so it
  shows a clear message instead of a spinner.
- 13:00 · FR-18 — build the offline-edit failure case for an *existing*
  crew member: an edit made offline should queue locally and show "not
  saved", not the generic "No connection" notice with nothing kept.
- 15:00 · FR-16 — INBOX #5's VAPID keys are now set; verify the push flow
  end to end against the live configuration and flip FR-16 to `done` if
  it holds (the real-iPhone check stays out of scope, no device here).
- 17:00 · FR-4 — write ADR-001's remaining backend half: why FastAPI +
  Postgres over the abandoned Next.js + Supabase stack, and what the old
  repo had that this one still lacks.

`BACKLOG.md` had only 2 `ready`+ungated items (FR-20, FR-21), below the
3-item floor, so this brief also proposed FR-22 (pm, Q1/Q2 desk-research
proxy) in PR #73 (`docs/backlog-proposals-2026-09-18`, auto-merge
enabled). FR-20, FR-21, and FR-22 stay `ready` but unscheduled today —
only five shifts run; whichever of today's five items finishes early
should pull the next one from that trio rather than sit idle.

## pm
- summary: 09:00 shift delivered FR-21 (switching-cost teardown, docs/research/switching-cost-teardown.md, PR #75, auto-merge enabled) — now `done` in BACKLOG.md. Covers all five FR-2 incumbents: documented export functions (StudioBinder, SetHero, Croogloo confirmed from their own help centers; Yamdu and Movie Magic partial/version-gated) and two sourced lock-in signals (Yamdu's tiered contact-retention complaint, Movie Magic's proprietary schedule format). No forum/Reddit discussion of switching found despite four targeted searches — marked unverified, not assumed absent. Otherwise unchanged: FR-3 discovery plan stands (PR #11); FR-2 teardown stands (PR #8); FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for most external domains (confirmed again this shift for a non-vendor `fly.dev` host, so this is a proxy-wide policy, not a vendor-specific block); `WebSearch` works.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: 13:00 shift (frontend) delivered FR-18's remaining failure-case half: an edit to an existing crew member made offline now queues in IndexedDB (`frontend/src/editor/crewEdits.ts`), the row shows it with a "not saved" tag via an optimistic overlay, and it syncs automatically next time the Crew tab loads or on demand via a "Sync" button. PR #79 (`feat/fr-18-crew-offline-edit-queue`), awaiting founder merge (touches `frontend/`). FR-18 stays `in-progress`: the photo bullet remains gated on INBOX #4. Earlier, 11:00 shift (frontend) delivered FR-11's remaining dod bullet: the crew-link failure case for a call sheet that no longer exists or isn't public. `loadCallSheet` (`frontend/src/loader.ts`) now returns a distinct `not_found` result on an HTTP 404, checked before the generic error path, with no cache fallback; `App.tsx` shows a plain "does not exist or is not available any more" message instead of the network-error copy that used to invite a pointless retry. The backend has no separate "not public" concept yet — `_get_call_sheet_or_404` 404s for both cases, so both collapse to the same message by design, noted in the PR for whoever adds real visibility control later. PR #77, awaiting founder merge (touches `frontend/`). FR-11 set to `done`. FR-8's own 09:00 verification task (iOS Safari SW registration over the real Fly-hosted HTTPS URL) was already reported skipped this morning — unchanged, still `in-progress`.
- tests: 13:00 shift — 11/11 `test_editor_e2e.py` pass, one new (`test_crew_edit_offline_queues_locally_and_shows_not_saved`); wider frontend E2E suite 29/30 (one pre-existing, unrelated geocoding-test failure — Nominatim blocked by this sandbox's egress proxy). 11:00 shift — 13/13 frontend Playwright tests passed (`frontend/tests/test_smoke.py`, one new).
- blockers: none new. Carried over: FR-18's photo upload gated on INBOX #4, FR-16's push gated on INBOX #5.
- needs_approval: yes — PR #79 and PR #77 both need the founder's own merge (code, not state); INBOX #5 (VAPID keypair) and INBOX #4 (Supabase Storage bucket/secret), both carried over, both needing the founder's own credentials.

## security (gate)
- summary: unchanged this shift; FR-7 stands `done` (re-verified 2026-09-16 17:00, 88/88 backend tests). FR-5 (the gate checklist itself) confirmed merged (PR #59, part of the overnight 2026-09-17 clearing) and stands `done`.
- tests: n/a — no code touched this shift.
- blockers: none.
- needs_approval: no.

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

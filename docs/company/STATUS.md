# Status

Updated: 2026-09-21 09:00 (09:00 shift)

## today

Five items qualify (`ready`, or `in-progress` with a note naming
remaining ungated work, `gated: no`/`partial`, dod not dependent on a
still-open PR), taken in `BACKLOG.md` priority order:

- 09:00 · FR-8 — verify the PWA's service worker actually registers over
  the real deployed Fly-hosted HTTPS URL on iOS Safari (not just the
  GitHub Pages demo bundle), closing ADR-002's one unverified failure
  case. Note: the last two attempts (09:00 and 15:00, 2026-09-18) hit
  this session's egress proxy 403'ing `fly.dev`/`api.fly.io` outright; if
  that repeats, the shift should skip per contract and take the next
  ready+ungated item.
- 11:00 · FR-16 — with INBOX #5's VAPID keys now set, verify the push
  flow end to end against the live Fly-hosted configuration and flip
  FR-16 to `done` if it holds (same egress caveat as FR-8 above).
- 13:00 · FR-6 — write `docs/marketing/positioning.md`, grounded in FR-1's
  corrected brief and FR-2's teardown (both `state: done`; FR-1's own PR
  #81 is still open, so this shift should pull its content from that
  branch rather than assume it is on `main`).
- 15:00 · FR-20 — Prague market sizing (`docs/research/prague-market-sizing.md`),
  answering BRIEF.md Q5 from public listings.
- 17:00 · FR-22 — desk-research proxy for BRIEF.md Q1/Q2
  (`docs/research/call-sheet-role-and-tooling-signals.md`), the same
  public-source-proxy convention FR-21 used for Q6.

`BACKLOG.md` has exactly 3 `ready`+ungated items (FR-6, FR-20, FR-22) —
at the 3-item floor, not below it, so no backlog-refill PR this morning.

**09:00 update**: the three PRs the morning brief flagged as open since
Friday (#79 FR-18, #81 FR-1, #83 FR-4) were all merged by the founder
between the 08:00 brief and this shift starting (confirmed: `gh pr list
--state open` is empty; `git fetch origin main` shows all three commits
— `a0f8138`, `70e7032`, `0656687` — on `main`'s head). Nothing is skipped
for depending on an open PR.

Took the plan's own first item, **FR-8** (verify the PWA service worker
over the real Fly-hosted HTTPS URL on iOS Safari): still undoable —
`curl -v` to both `filmrunner-api.fly.dev` and `api.fly.io` confirmed the
same 403 CONNECT-tunnel rejection this session's egress proxy has hit on
every prior attempt since 2026-09-14. FR-8 stays `in-progress`, unchanged.
Skipped per the shift contract. Did not separately re-test **FR-16**
(11:00's planned item, also gated on reaching the same
`filmrunner-api.fly.dev` host) — the identical domain was just confirmed
blocked seconds earlier in the same shift, so a second curl would only
repeat the same result; treated as skipped for the same reason and noted
here rather than re-run. FR-16 stays `in-progress`, unchanged.

Took the next-highest-priority ready+ungated item instead: **FR-6**
(positioning draft, marketing). `docs/marketing/positioning.md` delivered:
four alternatives considered (AI-speed per the June brief's own H4 claim,
delivery tracking, Prague-locality, live+offline-honest), each with a
reason for or against, grounded in `BRIEF.md`'s working hypothesis/H1-H5
and `competitive-teardown.md`'s per-incumbent findings. Chose
live+offline-honest. Addressed the dod's failure case directly:
StudioBinder already markets a "living" call sheet (FR-2), so the doc
narrows the claim to the conjunction with offline-honesty, since FR-2
found StudioBinder's own offline support only described as "in the
pipeline" (unverified, not shipped) and no incumbent verifiably ships
both; names the revisit trigger if that changes, and flags that FR-3's
Q3 pain list doesn't name "offline-honest" verbatim, so the position
needs re-testing against real interview data once FR-3 unblocks. Marked
explicitly as a hypothesis for FR-3 to test, per `BRIEF.md`'s own kill
criterion. PR #86 (`docs/fr-6-positioning-draft`) — touches
`docs/marketing/**` and `BACKLOG.md`'s state line only, so per `TEAM.md`
this qualifies for auto-merge; enabled. FR-6 set to `done` in
`BACKLOG.md` — the PR is the whole deliverable.

**17:00 update (2026-09-18, prior day)**: took the plan's own item, **FR-4** (tech-lead): wrote
the remaining backend half of ADR-001, `docs/adr/ADR-001-backend-stack.md`
(the frontend half was already written 2026-09-14). States the three
options considered (keep the old Next.js + FastAPI + Supabase repo, this
FastAPI + Postgres skeleton, a hybrid vendoring the old repo's auth
code), the decision (this skeleton, citing `DECISIONS.md` 2026-09-14),
and — the dod's harder bullet — what the old repo had that this one
lacks: script-to-breakdown AI drafting, RLS-based authorization,
budgeting, deeper scheduling depth, and a general change-log feed, each
with the specific BRIEF.md trigger that would justify porting it, cited
directly against the June 2026 brief's real content
(`docs/reference/PRODUCT_BRIEF-2026-06.md`, verified in full by this
same day's 15:00 shift, so this ADR could cite it rather than guess).
Names the failure-case revisit trigger the dod asks for: a future ADR
supersedes this one if a hard BRIEF.md requirement contradicts the
choice, rather than editing this decision in place. Cross-linked with
`ADR-001-frontend-stack.md`. PR #83 (`docs/fr-4-adr-001-backend-half`) —
touches `docs/adr/`, so per `TEAM.md` this needs the founder's own merge,
no auto-merge. All three dod bullets are now delivered, so FR-4 is set
to `done` in `BACKLOG.md` (the PR is the whole remaining deliverable).
`gh pr list --state open` before this shift showed #79 (FR-18) and #81
(FR-1), neither of which FR-4 depended on, so nothing was skipped for
depending on an open PR. Also noted: PR #77 (FR-11) was merged by the
founder herself at 09:27 today, so FR-11 needed no further action.

**15:00 update**: the plan's own item, **FR-16** (verify push end to end
against the live Fly-hosted configuration), was undoable this shift: both
`filmrunner-api.fly.dev` and `api.fly.io` are rejected outright (403) by
this session's egress proxy, confirmed with `curl -v`, the same class of
block FR-8's iOS check hit this morning — no `fly` CLI is installed here
either, so there is no path to check even secret *presence* without
hitting the network. FR-16 stays `in-progress`, unchanged. Skipping per
the shift contract, and before moving to the next backlog item in
priority order, ran a plain local `find` for the June 2026 source brief
FR-1's note said the founder still needed to add. It was not missing:
`docs/reference/PRODUCT_BRIEF-2026-06.md` has been in the repo since
commit `b918215` (2026-09-14, the founder's own commit) — the same commit
that wrote `BRIEF.md`'s "could not open it" note. Every shift since had
repeated that claim by trying the old external repo path or a fetch this
environment blocks, never a local-tree check. Read all 166 lines and
rewrote `BRIEF.md`'s "Assumptions" section from the actual content: H1
corrected (the June brief explicitly cuts budgeting from its own v1 and
never mentions SSO — the opposite of the previous guess), H2 confirmed
(the brief argues for *keeping* Next.js+FastAPI+Supabase; the restart to
this repo's stack was a scope decision, not a technical finding), H3
replaced with the real figures (€99–499 tiered flat fee, unlimited crew,
free for film schools, Prague-first distribution), plus two new
hypotheses (H4 differentiation claim, H5 guardrail consistency). Every
claim cites a section of the source and is dated 2026-09-18; nothing is
asserted as fact, all of it stays hypothesis pending FR-3 (still blocked
on INBOX #1). PR #81 (`docs/fr-1-verified-source-brief`) — touches
`docs/company/BRIEF.md` and `DECISIONS.md`, so per `TEAM.md` this needs
the founder's own merge, no auto-merge. FR-1 set to `done` in
BACKLOG.md; FR-6 (positioning, marketing) unblocked from `blocked` to
`ready` since both FR-1 and FR-2 are now done (not worked this shift).
The process gap itself (a stale "could not access" claim going
unchecked for four days) is recorded in `DECISIONS.md` so a future shift
checks the local repo before accepting a similar claim. `gh pr list
--state open` shows only PR #79 (FR-18, unrelated), so nothing else was
skipped for depending on an open PR.

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
  **Skipped**: the live Fly URL is 403'd by this session's egress proxy,
  same gap as FR-8's; see the 15:00 update above. Took FR-1 instead
  (found the June 2026 source brief was already in the repo and closed
  its remaining dod bullet) — highest-priority actionable item once
  FR-16, FR-8, and FR-17/FR-18/FR-1's-then-believed blocker were ruled
  out.
- 17:00 · FR-4 — write ADR-001's remaining backend half: why FastAPI +
  Postgres over the abandoned Next.js + Supabase stack, and what the old
  repo had that this one still lacks. Now unblocked from guesswork too:
  the 15:00 shift's BRIEF.md correction confirms the June brief argues
  for *keeping* Next.js+FastAPI+Supabase, so FR-4 can cite that directly
  instead of treating it as unverifiable.

`BACKLOG.md` had only 2 `ready`+ungated items (FR-20, FR-21), below the
3-item floor, so this brief also proposed FR-22 (pm, Q1/Q2 desk-research
proxy) in PR #73 (`docs/backlog-proposals-2026-09-18`, auto-merge
enabled). FR-20, FR-21, and FR-22 stay `ready` but unscheduled today —
only five shifts run; whichever of today's five items finishes early
should pull the next one from that trio rather than sit idle.

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

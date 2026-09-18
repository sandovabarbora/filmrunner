# Status

Updated: 2026-09-18 08:00 (morning brief)

## today

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
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo. Morning brief's FR-21 backlog proposal (PR #66) still open and unmerged.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch`/`WebSearch` remain blocked by this session's egress proxy for most external domains.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: 17:00 shift — idle, same reason as 09:00/11:00/13:00/15:00 (see `## today`). Re-checked `gh pr list --state open`: #55 (`fix/alembic-merge-heads`), #58 (backlog proposals, FR-20), #59 (FR-5 checklist, doc-only, awaiting merge), #66 (backlog proposals, FR-21) — all unchanged all day, all open, no INBOX approval to merge any of them. Carried over: FR-18's photo upload gated on INBOX #4, FR-16's push gated on INBOX #5. Last scheduled shift of the day; day summary follows.
- tests: n/a — no code touched this shift.
- blockers: PR #55 (migration-head fix, worth doing before the next deploy), #58, #59, #66 all unmerged all day.
- needs_approval: yes — INBOX #5 (VAPID keypair) and INBOX #4 (Supabase Storage bucket/secret), both carried over, both needing the founder's own credentials.

## security (gate)
- summary: unchanged this shift; FR-7 stands `done` (re-verified 2026-09-16 17:00, 88/88 backend tests). FR-5 (the gate checklist itself) delivered 2026-09-16 09:00 (PR #59), still awaiting founder merge.
- tests: n/a — no code touched this shift.
- blockers: none.
- needs_approval: no.

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

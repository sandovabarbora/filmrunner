# Decisions

Append-only. Format: date, decision, why, revisit when.

## 2026-09-14: canonical code is this skeleton, not the old repo
- Decision: FilmRunner is rebuilt on this repository (FastAPI + SQLAlchemy +
  Alembic + Postgres backend, single-file offline PWA). The old codebase at
  `~/Documents/Coding/sandbox/film_production` (Next.js + FastAPI +
  Supabase, June 2026 brief, studio-readiness work) is reference material.
- Why: founder's explicit choice for a conscious restart around the call
  sheet; the old repo accumulated surface area without a validated wedge.
- Revisit when: BRIEF.md v1 needs a capability the old repo already has and
  this one does not (then port, do not switch).

## 2026-09-14: strategy is founded from scratch
- Decision: the June 2026 PRODUCT_BRIEF.md is an input, not the constitution.
  BRIEF.md starts as open questions answered by discovery.
- Why: founder's call; the earlier thesis was never validated with customers.
- Revisit when: never automatically; BRIEF.md v1 supersedes this note.

## 2026-09-14: company brain lives in the repo as markdown
- Decision: `docs/company/` is the single source of truth; no Notion mirror.
- Why: versioned, greppable, readable by cloud routines with zero context;
  one place of truth.
- Revisit when: the founder needs mobile browsing of backlog badly enough
  to justify a read-only mirror.

## 2026-09-14: approvals via INBOX.md, digest via Gmail
- Decision: the routine emails a daily digest to the founder only; approval
  state lives in `INBOX.md`.
- Why: works from a phone, no new tooling, the Gmail connector is available
  to cloud routines.
- Revisit when: digests are ignored for two weeks (then weekly) or approvals
  pile up (then a faster channel).

## 2026-09-14: one daily shift, roles as disciplines
- Decision: a single cloud routine per day working one backlog item, roles
  chosen per item; not one routine per role.
- Why: shared context, no PR collisions, no roles inventing work to fill a
  daily report. One-per-role is the evolution once the backlog per role is
  deep.
- Revisit when: the digest routinely reports "nothing to do" (go weekly) or
  the queue never drains (split by role).

## 2026-09-14: first work is discovery, not features
- Decision: the first six backlog items are brief, teardown, discovery plan,
  stack ADR, CI gates, positioning. No product features until BRIEF.md v1.
- Why: building features against an unvalidated thesis is the trap the old
  repo fell into.
- Revisit when: BRIEF.md reaches v1.

## 2026-09-14: main accepts only CI-green commits, state files go via auto-merged PRs
- Decision: ruleset "main: ci required" (id 23282045) requires the `ci` status check on every commit reaching main. Verified: this rejects direct pushes outright ("Required status check ci is expected"), so the routine cannot commit STATUS/INBOX/LOG straight to main as the spec first said. Instead the routine opens a state-only PR on branch `shift/state-<date>` and enables auto-merge (`gh pr merge --auto --squash`); it lands when ci is green. Code PRs are never auto-merged by the routine.
- Why: enforced beats agreed; a three-minute delay on state updates costs nothing, and the digest email is the live channel anyway.
- Revisit when: state PRs pile up unmerged (ci flaky) or the founder wants state changes instantly visible on main.

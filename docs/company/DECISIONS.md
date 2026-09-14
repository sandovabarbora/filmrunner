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

## 2026-09-14: first routine run, what it proved and what changed
- Decision: the routine keeps the Artifact tool (allow-listed) and gains WebSearch/WebFetch; the prompt tells it never to wait on a permission prompt.
- Why: run cse_013HbrCVEvh1npHTE199Lou4 behaved per contract on FR-1 (PR #5, no invented content, in-progress not done, asked for the missing source) but then blocked on an unanswered permission prompt for the board write, so no state PR and no digest were sent. Research items need the web to cite sources.
- Also: repository merges restricted to squash with the commit title, so `main` history reads as commit messages, not "Merge pull request #n".
- Revisit when: a run again stalls on any prompt (then remove the tool rather than tune the prompt).

## 2026-09-14: branch and commit conventions, enforced in CI
- Decision: branches `<type>/<what-it-does>` (feat, fix, docs, chore, refactor, test, ci); commits and PR titles in Conventional Commits form; `main` squash-only with the commit title. `scripts/check_conventions.py` runs on every PR.
- Why: founder's call; a convention the linter enforces survives, one that lives in a doc does not.
- Revisit when: a type is missing often enough that people reach for `chore` as a catch-all.

## 2026-09-14: the routine does not touch the status board
- Decision: Artifact removed from the routine's tools; the board is synced by interactive sessions.
- Why: two runs (cse_013HbrCVEvh1npHTE199Lou4, cse_015G75GF4eJwZJ6FrhfxDSCv) stalled on the Artifact permission prompt even with the tool allow-listed; a stalled run also never sends its digest.
- Revisit when: routines can pre-approve Artifact writes.

## 2026-09-14: the daily shift is verified end to end
- Decision: routine v3 (trig_012VzQ17vcMx1FwKu4ZSYYBC) is the production operating loop. Run cse_01UhjcTrP22PUegDgdo7z9qK proved the full cycle: clone, FR-3 delivered on `docs/fr-3-discovery-plan` (PR #11), gated part filed as INBOX #1, state PR `chore/shift-state-2026-09-14` (#12) with auto-merge, digest emailed at 11:19 UTC to the founder only.
- Why: three runs were needed; the first two stalled on the Artifact permission prompt and never reached the digest step. Removing the tool fixed it.
- Learned: cloud runs use the founder's GitHub identity (mergedBy shows her login either way), so "who merged" must be read from the run log, not from GitHub; WebFetch is egress-blocked for most vendor domains, WebSearch works.
- Revisit when: a run stalls again for any reason, or digests start arriving without a matching state PR.

## 2026-09-14: working hours are 08:00 to 18:00 Prague, Monday to Friday
- Decision: replace the single 05:00 shift with a morning brief at 08:00 (plans the day, refills the backlog via a proposals PR, emails the plan) and five two-hour shifts at 09, 11, 13, 15, 17. Shifts email only when productive; the 17:00 shift sends the day summary. Founder's call ("klasicky 9 až 6", every two hours).
- Why: the founder wants a team that visibly works during the day, not one night run; two-hour spacing halves cost and review load versus hourly.
- Cost: up to six runs per weekday on Sonnet. Revisit when: the day summary reports three or more idle shifts for a week (drop to every four hours) or PRs pile up unreviewed (drop a shift).

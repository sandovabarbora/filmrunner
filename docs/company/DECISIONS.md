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

## 2026-09-14: build the working vertical slice now, discovery in parallel
- Decision: overrides the morning's "no product features until BRIEF.md v1". The team builds toward one working loop, AD publishes a call sheet, crew opens a link on a phone, it works offline, a hot revision propagates. Backlog order: FR-8 (hosted API + DB) → FR-10 (AD editor) → FR-11 (share link + QR) → FR-7 (security fixes) → FR-12 (real auth) → FR-9 (offline-honest status). Discovery (FR-3, INBOX #1) runs in parallel on the founder. ADRs and the gate checklist (FR-4, FR-5) move down.
- Why: founder's call ("musíme mířit na working věc"). The demo on GitHub Pages (PR #17) made the gap visible: the viewer exists, the AD side does not. A working slice is also the strongest artefact for the interviews.
- Guardrail kept: every item cites the BRIEF question it serves in its `why`; anything that needs accounts or money stays gated through INBOX.
- Revisit when: interviews (FR-3) contradict the AD-as-operator assumption; then the editor is re-scoped before more is built on it.

## 2026-09-14: Supabase for hosted Postgres (and later Auth), not Neon
- Decision: the hosted database is Supabase Postgres, used as plain Postgres through SQLAlchemy + Alembic. Supabase Auth is the leading candidate for FR-12. No Supabase-specific schema features (RLS as business logic, edge functions, storage) in the data model.
- Why: founder knows it from the old repository; Auth with magic links makes FR-12 configuration rather than code; Realtime fits the living call sheet later. Neon was a default, not a considered choice. Guardrail: keep the model portable so the old repo's vendor sprawl does not repeat.
- Known cost: free-tier projects pause after a week of inactivity; mitigate with a scheduled health ping from CI or accept until there are real users.
- Revisit when: the free tier pause bites a demo, or a feature tempts us into Supabase-only logic.

## 2026-09-18: the June 2026 product brief was in the repo the whole time
- Decision: none — a correction to the record. `docs/reference/PRODUCT_BRIEF-2026-06.md`
  has existed in this repo since commit `b918215` (2026-09-14 15:54 CEST,
  the founder's own commit), but `BRIEF.md`'s "Assumptions" section — written
  in that same commit — said the source could not be opened, and every
  shift through 2026-09-18 09:00 repeated that claim without checking
  `docs/reference/` in the local checkout; they instead tried the old
  external repo path or a fetch that this environment's egress policy
  blocks. The 15:00 shift on 2026-09-18 found it with a plain `find`,
  read it in full, and rewrote `BRIEF.md`'s assumptions from the real
  content (FR-1, now `done`).
- Why: four days of shifts treated an unreachable-source claim as settled
  without re-checking it, because "unreachable" sounded like an
  environment limit (like the `fly.dev` egress block FR-8/FR-16 hit) and
  nobody tested that assumption against the local filesystem specifically.
- Revisit when: never scheduled — this is the fix. General lesson for any
  future "could not access X" note: check the local repo tree directly
  before accepting it, since a teammate may have already added the file.

## 2026-09-17: auto-merge by reversibility, and idle shifts propose work
- Decision: PRs touching only reversible documents (state files, backlog proposals, research, marketing, gate checklists, PR template) auto-merge after CI; code and decision documents (ADRs, BRIEF, TEAM, DECISIONS) still wait for the founder. A shift with no workable item proposes one backlog item as pm. The brief lists PRs waiting more than a working day.
- Why: 2026-09-16 and 09-17 the team idled ten shifts: the only `ready` item depended on an open docs PR and two proposal PRs waited for a merge nobody was around to give. The founder's attention is the scarce resource; it should go to code and decisions, not to research documents she can edit at will.
- Revisit when: an auto-merged proposal sends a shift down a path the founder did not want (then tighten the proposal rules, not the auto-merge).

## 2026-09-21: hackathon week, everything with green CI auto-merges
- Decision: from 2026-09-21 to 2026-09-25 every PR with a green `ci` check auto-merges, code and ADRs included; only TEAM.md waits for the founder. Shifts run hourly 09 to 17. Accounts, money, secrets, deploys and third-party email stay gated. Backend PRs announce "deploy needed"; deploys stay on the founder's machine or her session.
- Why: founder's call ("udělejme hackathon, mergujme automaticky"); the review gate on code was the remaining bottleneck and CI (backend, E2E on a real API, conventions, one Alembic head) is the safety net this week.
- Revisit: 2026-09-25 evening; the reversibility rule returns automatically unless extended.

## 2026-10-01: the 2026-09-14 shift-cadence revisit trigger is met, but by a confound, not by cadence itself (FR-119)
- Finding: the 2026-09-14 "working hours" entry's own revisit trigger ("PRs pile up unreviewed (drop a shift)") reads as literally met today. `list_pull_requests --state open` shows seventeen code/workflow/decision PRs (#241, #245, #247, #249, #251, #260, #262, #265, #267, #274, #278, #280, #282, #288, #299, #301, #303); the oldest, #241, opened 2026-09-28 07:24 UTC — over three working days ago. The count has only grown, never shrunk, across every shift's own note since: roughly 5 at 2026-09-28's close, 9 at 2026-09-29's, 13 at 2026-09-30's, 14 at this morning's 08:00 brief, 17 by this shift. In that entire span, zero code/workflow/decision PRs have been merged by the founder — every shift's own `list_pull_requests` check says "none newly resolved."
- Confound checked, per this item's own dod: the 2026-09-14 entry's cadence is five two-hour shifts (09, 11, 13, 15, 17 Prague); what has actually run all week is hourly (09 through 17, nine shifts/day) — confirmed directly, not inferred, since this very shift's own fired prompt still reads "hourly 09 to 17 Europe/Prague this week," the exact leftover FR-104/PR #262 (still open, unmerged) already found and fixes at the prompt-text level. A roughly 1.8x higher shift rate alone materially inflates PR-creation rate: most days this week delivered more plan items than that day's own five-slot plan named, each one run ahead of its nominal slot. Whether the registered cron trigger itself (`trig_012VzQ17vcMx1FwKu4ZSYYBC`) was also left on an hourly schedule from the 2026-09-21 hackathon week, rather than just the prompt's own self-description, is not directly checked here — this routine has no tool to read the trigger's own registration, only to observe that it is in fact firing hourly — but either way only the founder can edit it (TEAM.md's own Runbook), a PR cannot.
- Conclusion: the trigger's literal text is met, but its named remedy (drop a shift, i.e. go below the documented cadence) treats the wrong cause — the cadence has never actually run at the documented rate to drop from this week. The more direct fix is restoring the documented every-two-hours cadence (merge PR #262 for the prompt's own logic, and separately revert the trigger's registered cron, a founder-only action at https://claude.ai/code/routines). That alone would roughly halve future PR-creation rate but would not, by itself, clear the PRs already open: a zero-merge rate over four working days is not a cadence artifact, since a founder review action does not depend on how many shifts ran. Filed as INBOX #8 rather than decided here.
- Revisit when: the cron is corrected and a further full week still shows net PR growth (then the trigger is genuinely about review capacity, not cadence); or the founder declares hourly the intended new normal, in which case this entry and the 2026-09-14 "working hours" table should be updated together rather than left as an unreverted hackathon-week artifact.

## 2026-11-05: a published shoot day can change date
- Decision: the date of a published day is no longer fixed. Moving or swapping days goes through `app/services/replan.py`, always as a new revision on every day touched, in one transaction. Revisions stay immutable; `CallSheet.shoot_date` is the current date and `CallSheetRevision.shoot_date` is what each revision was published for.
- Why: outreach to production companies named a sudden plan change as the biggest pain, and "cancel and create a new day" loses the revision history, the read receipts and every personal link's continuity.
- Revisit when: pilots show ADs reschedule ranges of days rather than single days or pairs.

## 2026-11-05: the confirm action follows the changes and rests at the bottom of the screen
- Decision: `.confirm` stays after the change list and is `position: sticky; bottom: 0`, not above the list. Margin asterisks are removed. The revision colour stays on the badge and the change block.
- Why: above the list it would invite a confirmation before reading, which is the thing confirming exists to prevent. Asterisks sat inline, their key was far away and they skipped changed times, while the list already says what changed.
- Revisit when: pilot data shows people confirm without opening "more changes" and then miss something that was folded.

## 2026-11-05: the visual world is a film still with the time as its title
- Decision: dark graded ground, one still per day, Archivo as the only typeface, revision colour only on the label and the confirm action. Replaces the cream paper and the revision-coloured change block. Stills are generated and must not be presented as real locations.
- Why: the founder rejected the paper look outright. The first round of three flat directions was also rejected; the chosen direction came from their saved references (A24, Kookie, Secret Level).
- Revisit when: crew report the dark screen is hard to read in daylight, or a production wants its own location photos.

## 2026-11-06: test personas are ordinary users of throwaway films
- Decision: seven taps on the logo open a test environment open to anyone. A persona gets a signed token for a user who is a member of test films only. Five taps still open admin access. A test film cannot gain real members, and a real film cannot gain a test persona.
- Why: a hidden gesture is not protection, so the isolation has to hold for anyone who finds it. Reusing membership means no access rule needs a test exception to get wrong.
- Revisit when: test worlds put visible load on the database, or a real pilot makes a public write endpoint unwelcome; one setting turns it off.


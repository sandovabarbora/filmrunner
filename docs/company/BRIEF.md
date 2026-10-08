# FilmRunner brief (v0.1, 2026-09-14)

Status: open questions, sharpened. Nothing here is decided except what
`DECISIONS.md` records. The June 2026 `PRODUCT_BRIEF.md` (old repo) is one
input among several, not a conclusion — see the access note below before
trusting anything attributed to it.

v0.1 changes from v0: each open question now has a concrete, testable
method instead of a category label; the kill criteria are stated as
numeric thresholds; a new section separates what we actually know (this
repo) from what we assume the old brief said but cannot currently verify.

## Working hypothesis (to be tested, not assumed)

A shoot-day call sheet that is live, offline-honest, and lands in every
crew member's pocket is a wedge into film production software. Owner of
the problem: the person who assembles and distributes call sheets.

## Open questions, each with an owner and how it gets answered

| # | Question | Owner | How we answer it (sharpened) |
|---|---|---|---|
| Q1 | Who actually assembles the call sheet on Czech productions: 1st AD, 2nd AD, production coordinator? Does it differ by production size? | pm | FR-3 discovery interviews (n≥5). Script asks separately who *drafts* times/locations, who *approves*, and who *distributes* — these can be three different people. Code each answer by production size (short <15 crew, feature <50, feature/TV >50). |
| Q2 | What do they use today and what does it cost them in hours per shoot day? | pm | FR-3 interviews: name the exact tool/workflow (e.g. email+PDF, WhatsApp, StudioBinder) and the elapsed time from "shooting schedule locked" to "call sheet in every crew member's hand". Cross-check named tools against FR-2's teardown. |
| Q3 | What goes wrong most often (late revisions, wrong call times, no signal on location)? | pm | FR-3 interviews: present a candidate list (late revisions, wrong call times, no-signal locations, crew missing an update, printing cost/waste) and ask the interviewee to rank their top 3 unprompted first, then confirm/add from the list. |
| Q4 | Who pays: the production company, the producer's line item, or the AD personally? At what price does it stop being a no-brainer? | pm | FR-3 interviews: ask who currently owns the budget line for production software. Test a price ladder (free / low tens of USD per month / roughly what FR-2 shows incumbents charge) and ask which tier the interviewee could expense without a second approval — that tier is the "no-brainer" ceiling. |
| Q5 | Is Prague dense enough for word-of-mouth distribution, or is the first market elsewhere? | marketing | Define "active production" as one that issued a call sheet in the last 30 days. Count via Czech Film Commission listings, FAMU productions, and any public filming-permit data. Compare the count against the sample size word-of-mouth distribution typically needs (cite the source used when this is done — do not assert a threshold without one). |
| Q6 | Which existing tool would we have to displace, and what would make an AD switch mid-season? | pm | FR-2 teardown names the incumbent per production size. FR-3 interviews then ask directly: "what would have to be true for you to switch tools mid-production?" — listen for data lock-in, muscle memory, or the tool being provided free by the production company. |
| Q7 | What is the smallest thing that proves the wedge: a call sheet viewer, a distributor, or a script-to-call-sheet flow? | pm + tech-lead | After Q1–Q3 answers exist, score three candidate MVP shapes (viewer only, distribution only, generation from an existing schedule) against: data the crew must already have, and rough build time. Decide only once real interview data exists — not before. |

## Assumptions carried over from the June 2026 product brief (verified 2026-09-18)

Correction: every prior version of this section said the June 2026 brief
could not be read. That was wrong from the start — the founder copied it
into this repo, verbatim, the same day as founding: commit `b918215`
(2026-09-14 15:54 CEST) added `docs/reference/PRODUCT_BRIEF-2026-06.md`
in the same commit that wrote this file's previous "unverified" wording,
and it has been sitting there, readable, through every shift since. No
prior shift's search for it (a `WebFetch`/`open` against the old repo
path, or against the file by a different name) happened to check
`docs/reference/` in this checkout directly. Flagged here so the process
gap — checking the local tree before declaring a source unreachable — is
visible, not just fixed silently; also recorded in `DECISIONS.md`.

What follows replaces H1–H3 with what the document (166 lines, read in
full 2026-09-18) actually says. It is still a June 2026 hypothesis, not
a BRIEF.md conclusion — nothing here is validated by a real interview
(FR-3) yet, and the June brief itself is explicitly reference material,
never a source of truth (see `TEAM.md`).

- H1 (revised): the June brief's scope is broader than today's
  call-sheet wedge, but not in the shape previously guessed. It targets
  the full chain "script → breakdown → schedule → call sheet → shoot
  day" with AI drafting the breakdown and schedule from a pasted script
  ("invisible glue", never branded as AI) — not a "studio-readiness"
  platform of auth/SSO plus budget/scheduling modules. **Budgeting and
  cost tracking are explicitly cut from v1** in the source ("producers
  keep their spreadsheets... trust in numbers takes years to earn"), the
  opposite of what the previous H1 guessed. SSO is not mentioned; the
  architecture section says only "salvage the hardened backend organs:
  auth deps, RLS, security work" — ordinary auth, not an SSO scaffold.
  Relevant to Q7 (smallest thing that proves the wedge): the June brief's
  own answer was "generation from an existing (AI-drafted) schedule", one
  of the three candidates Q7 already asks FR-3 to score against real
  interview data, not assumed here.
- H2 (confirmed): the earlier build's chosen stack was Next.js + FastAPI
  + Supabase, and the brief explicitly argues for *keeping* it ("salvage
  the hardened backend organs... no new infrastructure services until a
  pilot forces them") — the restart to this repo's FastAPI + Postgres +
  React skeleton was the founder's scope decision (2026-09-14,
  `DECISIONS.md`), not a finding that Next.js or Supabase were technically
  wrong. `docs/adr/ADR-001-frontend-stack.md` and FR-4's still-open
  backend half should cite this directly rather than guessing at it.
- H3 (revised): concrete figures the June brief does state, as hypotheses
  for Q4 and Q5 to test, not facts: a **per-production flat fee, tiered
  by size, "e.g. €99–499", unlimited crew** (contrasts with a per-seat
  model); **free for film-school productions** (FAMU, Zlín) as a
  deliberate farm-system channel; distribution leads with **Prague/CZ
  first**, matching Q5's own premise that Prague density is worth
  testing. No customer quotes are in the document — it is a founder/
  mentor strategy session brief, not interview output, so it carries no
  more weight than any other hypothesis until FR-3 tests it.
- H4 (new, rechecked 2026-10-08 — FR-150): the brief's differentiation claim
  is speed and AI-assisted generation ("script to a call sheet in everyone's
  pocket in 30 minutes... nobody can demo this today — not Movie Magic, not
  StudioBinder, not Yamdu"). The recheck this note asked for is done: see
  `competitive-teardown.md`'s "H4 recheck" section. Result is mixed, not a
  clean confirmation — **full script-to-schedule AI generation (a schedule
  drafted by AI from a script, no human in the loop) is still offered by
  none of the five incumbents**, so the broad wedge claim holds. But the
  claim as literally worded names "not Yamdu" for AI assistance generally,
  and Yamdu's own pages (checked directly, not a `WebSearch` snippet)
  confirm a real AI-assisted *script-breakdown* feature (character/
  location/prop tagging suggestions a human confirms), in beta since
  2025-10-28 — the step immediately before scheduling, not scheduling
  itself. H4 as worded is **confirmed false for that one claim** and should
  be narrowed to AI-assisted *scheduling* specifically before reuse in
  positioning copy; StudioBinder, SetHero, and Movie Magic Scheduling are
  confirmed absent even for breakdown (SetHero's own FAQ explicitly
  disclaims both), and Croogloo stays unverified (its features page is
  dead, the one page likely to state such a claim).
- H5 (new): the brief names explicit anti-scope-creep guardrails ("the
  chain stays thin", "depth at the end", "one operator: the 1st AD wins
  every conflict") that read as consistent with this repo's own
  `TEAM.md` product rule ("connect first, then add") and the working
  hypothesis at the top of this file, for whatever that consistency is
  worth as a sanity check, not as independent validation.

Nothing above is treated as decided; it is cited, dated, and left for
FR-3 interviews and the open questions above to confirm or kill.

## Kill criteria

- Of five Prague interviews (FR-3), fewer than 2 name call-sheet
  distribution among their top-3 pains (self-reported ranking from the Q3
  script) → stop and re-frame the wedge.
- No price tier in the Q4 ladder that any interviewee could expense
  without a second approval → stop; there is no plausible payer.
- A hypothesis that cannot be tested within a month of starting FR-3 is
  marked "parked" in this file, never deleted or silently treated as true.

## Out of scope until this brief is v1

New product features, landing page, pricing page, deployment, outreach
beyond interview invitations.

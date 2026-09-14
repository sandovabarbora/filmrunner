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

## Assumptions carried over from the June 2026 product brief (unverified)

This shift could not open `PRODUCT_BRIEF.md` or the old repository.
`DECISIONS.md` (written at founding) records that both live outside this
repository, at `~/Documents/Coding/sandbox/film_production` on the
founder's machine — a path this routine has no access to, and none was
found anywhere in this checkout either. What follows is reconstructed only
from `docs/company/DECISIONS.md`, not from the original document, and is
listed as unverified hypotheses, never as fact:

- H1: the earlier thesis assumed a broader "studio-readiness" platform
  (auth/SSO, budget tracking, scheduling), not a single-wedge call-sheet
  product. (source: `DECISIONS.md`, 2026-09-14 founding note)
- H2: the earlier build used Next.js + Supabase; it was abandoned for a
  conscious restart, not because those specific choices were shown to be
  wrong. (source: `DECISIONS.md`)
- H3: whatever specific customer quotes, pricing figures, or market-size
  numbers the June 2026 brief may contain are unknown to this shift. They
  are not reproduced here, and nothing above should be read as a summary
  of the document's actual content.

Action needed from the founder: to let a future shift verify or retire H1
and H2 against the source, add the brief (or its key sections) to this
repo, e.g. `docs/reference/product-brief-2026-06.md`.

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

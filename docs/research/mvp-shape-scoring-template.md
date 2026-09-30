# BRIEF Q7 — MVP-shape scoring template

FR-113. Role: pm. Date drafted: 2026-09-30 (12:00 shift).

## Purpose

BRIEF.md Q7: "What is the smallest thing that proves the wedge: a call
sheet viewer, a distributor, or a script-to-call-sheet flow?" Q7's own
method says to score three candidate MVP shapes against two dimensions
("data the crew must already have" and "rough build time") **after**
Q1–Q3 interview answers exist (FR-3, blocked on INBOX #1, still
`pending`), and to decide only once that real data exists — not before.

This doc is the empty instrument, not an early answer. It exists so that
the day FR-3 unblocks, filling in the scoring grid is a lookup against a
predefined definition, not a fresh judgment call invented on the spot. No
cell in the scoring grid below is filled in. Where this doc states a fact
about this repo's own code today (what is already built, what data model
already exists), that is a fact about the codebase, checked directly, not
a guess about what real productions have — those two are kept visibly
separate below so a future reader never mistakes a codebase fact for an
interview finding.

## The three candidates (verbatim from BRIEF.md Q7)

1. **Viewer** — a call sheet viewer.
2. **Distribution** — a distributor.
3. **Generation** — a script-to-call-sheet flow (generation from an
   existing schedule).

Each is defined precisely against this repo's own data model
(`backend/app/models/call_sheet.py`, `backend/app/models/production.py`)
so "which candidate" is never ambiguous when the scoring happens:

- **Viewer**: a crew member opens a link and reads an already-assembled
  `CallSheetRevision` — its `schedule_items`, `cast_calls`, `crew_calls`,
  linked `Location`/`Contact` rows. Nothing about *how* that revision got
  assembled is in scope; only reading it is.
- **Distribution**: the same already-assembled `CallSheetRevision`, but
  the system also gets it into every crew member's hand and tracks who
  has and hasn't seen it (`DistributionLog`, channel = email/SMS/link/push).
  Superset of Viewer: distribution without a way to view the result once
  delivered isn't a coherent candidate on its own.
- **Generation**: the system produces the `ScheduleItem`/`CastCallEntry`
  rows themselves from an upstream artifact (a script, or a locked
  shooting schedule) instead of a human typing each row into the editor.
  Superset of Viewer and, per BRIEF's own June-2026 source (`H1` in
  `BRIEF.md`), implicitly needs distribution too once generated content
  exists to send.

## Dimension 1 — data the crew must already have

**Definition (ready now):** for each candidate, what must exist and be
correct *before* the system does anything, and — this is the part only
FR-3 can answer — whether real Prague productions already have that thing
in a usable form today, or would have to create it for the first time to
use this candidate. The second half is exactly what FR-3 Q2 ("what do
they use today") is designed to surface; scoring this dimension without
that answer would be guessing at the door-height, not measuring it.

| Candidate | What must already exist (repo-fact, defined now) | Do real productions already have this today? (FR-3, pending) |
|---|---|---|
| Viewer | A fully assembled `CallSheetRevision`: every scene/location/day-night/page-count row, every cast and crew call time, entered by someone, somewhere, before a crew member can view anything. Viewer supplies none of this itself. | *(pending FR-3 Q2)* |
| Distribution | The same fully assembled `CallSheetRevision`, **plus** a current, correct `Contact` roster (phone/email) per `CrewMember`/`CastMember` — delivery routes on `DistributionLog.contact_id`, so a stale contact silently fails one person's delivery. | *(pending FR-3 Q2)* |
| Generation | An upstream artifact this repo's data model does not store today: a script (screenplay text) or a locked schedule in some existing form (PDF, spreadsheet, another tool's export). Nothing under `backend/app/models/` represents a script or an unstructured schedule — `ScheduleItem` already assumes each scene/location/day-night/page-count is *known*, which is exactly what generation would have to produce instead of require. | *(pending FR-3 Q2 — specifically, what form this artifact actually takes for a real production: paper, PDF, a spreadsheet, or another tool's export)* |

## Dimension 2 — rough build time

**Definition (ready now):** rough build time is scored relative to what
this repo already ships today, so "how much is left to build" is a
lookup against named, merged work, not a re-estimate from zero. This half
*is* a repo fact and could technically be filled in without FR-3 — it is
still left blank in the grid below, in keeping with Q7's instruction to
score (not partially score) only once real interview data exists, so a
later reader never has to untangle which cells were pre-decided and which
came from real evidence.

| Candidate | What already exists in this repo, as of 2026-09-30 (repo-fact, defined now) | Rough build time (score — pending FR-3) |
|---|---|---|
| Viewer | Ships today: `CallSheetView` (frontend), the personal crew link (FR-13, `?me=<token>`), the offline-honest PWA behaviour, and the full revision/schedule/cast/crew data model. | *(pending)* |
| Distribution | Ships today: push notifications (FR-16, FR-72 background delivery), the "who hasn't seen today's revision" history panel (FR-50) built on `DistributionLog`. Named gap, from the model's own docstring: actual email/SMS provider integration is explicitly out of scope for this skeleton — link and push channels work, email/SMS sending does not yet. | *(pending)* |
| Generation | Ships today: nothing. No script-ingestion, schedule-parsing, or AI-drafting code exists anywhere in `backend/` or `frontend/`. This is the one candidate with a genuinely unscoped build — a future backlog item should size it specifically once Q7 picks a direction, not guessed here. | *(pending)* |

## How to fill this in once FR-3 lands

1. Re-read BRIEF.md's kill criteria before scoring anything — if fewer
   than 2 of 5 interviewees name call-sheet distribution in their top-3
   (Q3), the wedge itself is in question, which matters more than which
   MVP shape wins.
2. For each interview, code the FR-3 Q2 answer ("what tool/workflow do
   you use today, and what does 'schedule-locked' already look like in
   your hands") against the "do real productions already have this
   today?" column above.
3. Only after all five are coded, fill the two pending columns per
   candidate. Do not average or force a single winner from partial data —
   if the five interviews split, say so plainly rather than picking a
   candidate on a slim majority.
4. This doc's own scoring grid is the record; do not duplicate the
   filled-in table elsewhere — update it in place and note the date and
   who filled it in, same convention as the rest of `docs/research/`.

## Failure case

If FR-3 interview data never materializes (INBOX #1 stays `pending`
indefinitely), this template stays exactly as-is: an empty, ready
instrument. No dimension in the scoring grid is pre-filled with assumed
or guessed interview data, and no candidate is declared a winner from
this doc alone — scoring is pending FR-3, not attempted early.

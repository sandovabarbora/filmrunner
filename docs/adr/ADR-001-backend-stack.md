# ADR-001 (backend half): FastAPI + SQLAlchemy + Alembic + Postgres, not the old Next.js + Supabase repo

Date: 2026-09-18. Status: accepted (restart already made 2026-09-14; this
records why, for FR-4). Companion to `ADR-001-frontend-stack.md`, which
covers the frontend half of the same stack decision; together they close
FR-4. Serves BRIEF.md's need for a recorded architecture decision rather
than an accident (`DECISIONS.md`, 2026-09-14 "canonical code is this
skeleton, not the old repo").

## Context

An old repository, `~/Documents/Coding/sandbox/film_production` (not in
this repo; its brief is copied at
`docs/reference/PRODUCT_BRIEF-2026-06.md`), already built toward a
broader "studio-readiness" platform: script breakdown, scheduling depth,
budgeting groundwork, and a Next.js + FastAPI + Supabase stack with, per
that brief's own architecture section (§8), "hardened backend organs:
auth deps, RLS, security work" already in place. The founder chose to
restart around a single wedge (the living call sheet) rather than
continue that build. This backend needed a stack decision independent of
the frontend rewrite (`ADR-001-frontend-stack.md`), since the API and
data layer are what every other backend item (FR-8, FR-12, FR-14, FR-15,
FR-19) is built on.

## Options

1. **Keep the old repo**, add the call-sheet wedge as a slice of it.
   Reuses the June brief's already-hardened auth (Supabase Auth + RLS)
   and Next.js API routes. Cost: inherits every acre of surface area the
   old brief scoped in (§5, §8) before any of it was validated — the
   founder's stated reason for restarting (`DECISIONS.md`, 2026-09-14)
   was exactly that the old repo "accumulated surface area without a
   validated wedge."
2. **This skeleton**: FastAPI + SQLAlchemy 2.0 + Alembic, plain
   PostgreSQL (Supabase used only as a hosted Postgres instance, never
   its RLS or edge functions as business logic — `DECISIONS.md`,
   2026-09-14 "Supabase for hosted Postgres"). A from-scratch data model
   scoped to exactly what the call-sheet wedge needs: productions, shoot
   days, revisions, crew, contacts. No inherited code, no inherited
   scope.
3. **Hybrid**: new frontend and data model, but vendor the old repo's
   auth/security modules directly. Rejected early — the old repo isn't
   in this checkout, and grafting one project's auth layer onto a
   different data model (this repo has no per-workspace/studio concept,
   only per-production) would mean adapting code written for a different
   authorization shape, not reusing it. No cost saving over designing
   auth against the actual model, which is what FR-12/FR-15 then did.

## Decision

Option 2. Backend is FastAPI + SQLAlchemy + Alembic + Postgres,
independent of the old repo's code (though not its ideas — see below).
Concretely: Postgres is Supabase-hosted but accessed as plain Postgres
over SQLAlchemy (`FILMRUNNER_DATABASE_URL`, the Supabase session
pooler); migrations run as a release step (ADR-002), never on boot; auth
is JWKS-verified Supabase Auth JWTs (ADR-004), not RLS-as-authorization —
RLS was explicitly ruled out as a business-logic mechanism so the
authorization model (per-production roles, ADR-005) lives in
`app/authz.py`, portable to any Postgres host.

## What the old repo had that this one lacks, and when to port

Per the June brief's own scope (§5, §8) and architecture section:

- **Script → breakdown AI drafting.** The June brief's headline demo
  ("paste script → AI drafts the breakdown"). This repo has no script
  ingestion at all. Not ported: BRIEF.md's own Q7 (smallest thing that
  proves the wedge) has not yet been answered by real interviews, and
  the June brief itself sequenced this as v1 scope, not a prerequisite —
  the wedge being tested first is call-sheet distribution, not
  generation. Port when Q7 is answered and points at generation as part
  of the wedge.
- **RLS-based authorization.** The June brief salvaged "hardened backend
  organs: auth deps, RLS, security work" (§8) from an even earlier
  build. This repo deliberately does not use RLS as business logic
  (`DECISIONS.md`, 2026-09-14): authorization is enforced in
  `app/authz.py` against per-production roles (ADR-005), verified with
  tests, so it is portable off Supabase if the Postgres host ever
  changes. Revisit only if `app/authz.py`'s dependency-based checks are
  ever shown to miss a case RLS would have caught at the database layer
  — a defense-in-depth argument, not a replacement.
- **Budgeting and cost tracking.** Explicitly cut from the June brief's
  own v1 (§5: "producers keep their spreadsheets... we don't ask for
  that trust yet"), so this is not something the old repo has that this
  one is behind on — both scope it out deliberately. Listed here only
  because BACKLOG.md's FR-4 dod names it; no port planned until BRIEF.md
  reaches v1 and a future brief revision puts it back in scope.
- **Scheduling depth beyond a shoot day's schedule items** (breakdown
  categorisation, script revision/colored-pages tracking, third-party
  integrations). Per the June brief itself (§5), explicitly sequenced
  *after* the first pilot and barred from blocking it. Not ported;
  revisit once FR-3's interviews validate the wedge and a pilot exists
  to sequence work after.
- **Event log for changes** (June brief §8: every change is an explicit
  event, crew sees a change feed). This repo has a narrower version —
  `DistributionLog` records publish/notification attempts (FR-16) and
  each publish is a new immutable revision (FR-10) — but there is no
  general change-feed the crew can browse ("call moved 7:00 → 7:30").
  Port when BRIEF.md Q3 interview data shows crew members want a
  history view, not just the current revision plus a push notification.

## Consequences

- Every backend item since (FR-7, FR-8, FR-12, FR-14, FR-15, FR-16,
  FR-18, FR-19) is built against this data model and auth shape with no
  code shared with the old repo; `docs/reference/PRODUCT_BRIEF-2026-06.md`
  is read for ideas and hypotheses (as FR-1 did for BRIEF.md), never for
  code to port directly.
- The Supabase-as-plain-Postgres boundary (no RLS, no edge functions,
  no Storage business logic beyond the one avatar bucket in FR-18) means
  the database can move to any Postgres host without touching
  `app/authz.py` or the SQLAlchemy models.
- The gap list above is a standing checklist: a future BRIEF.md revision
  that reintroduces script generation, budgeting, or deeper scheduling
  should check this ADR before treating that work as new scope.

## Failure case

If a hard requirement in BRIEF.md later contradicts this choice — for
example, FR-3 interviews show ADs need RLS-grade row isolation this
repo's dependency-based authorization cannot give within its complexity
budget, or the wedge itself turns out to require script-to-breakdown
generation before any pilot will use it — the trigger to revisit is named
here explicitly, not treated as grounds to rewrite this ADR after the
fact: open a new ADR that supersedes this one, citing the specific
BRIEF.md requirement and interview evidence, rather than editing this
document's decision in place.

## Revisit when

Any of the trigger conditions in "failure case" above are met, or BRIEF.md
reaches v1 with budgeting or script generation back in scope (see the gap
list above).

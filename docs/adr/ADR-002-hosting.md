# ADR-002: Hosting for the working slice

Date: 2026-09-14. Status: accepted (founder decision in session). Serves FR-8.

## Context

The PWA is on GitHub Pages (https://sandovabarbora.github.io/filmrunner/)
with a bundled demo. For a working slice the API and database must run
somewhere a phone can reach over HTTPS, at zero or near-zero cost, with
no operations burden on a solo founder.

## Options considered

| Layer | Chosen | Alternatives | Why |
|---|---|---|---|
| Frontend | GitHub Pages (workflow build) | Cloudflare Pages, Vercel | already live, free, HTTPS, builds from `main` |
| API | Fly.io, region `fra`, Dockerfile, `shared-cpu-1x` 256 MB, scale to zero | Railway, Render | existing Dockerfile works unchanged; release command for migrations; free-tier-sized; HTTPS |
| Database | Supabase Postgres (Frankfurt), used as plain Postgres | Neon, Fly Postgres, Railway | founder knows it; Auth with magic links is the FR-12 candidate; Realtime fits the living call sheet later. Neon was a default, not a considered choice |

## Decision

Fly.io for the API, Supabase for Postgres, GitHub Pages for the PWA.
Migrations run as Fly's `release_command` (`alembic upgrade head`), never
at container start. All API secrets live in Fly (`fly secrets set`).
Deploys are run by the founder from her machine (`cd backend && fly
deploy`), on purpose: no deploy-capable token is stored in GitHub. The
backend refuses to start outside `development` with the dev bearer token
(config validator, tested).

**Addendum 2026-10-02 (FR-109): report the deployed commit.** The deploy
command is now `cd backend && fly deploy --build-arg
FILMRUNNER_GIT_SHA=$(git rev-parse HEAD)` — one added flag, run from the
repo root so `git rev-parse` resolves, same single step. It bakes the
commit the image was built from into `/healthz`'s response
(`git_sha`), which `scripts/check_live_stack.py` compares against
`main`'s current HEAD (public GitHub API, no token) in the daily "pilot
readiness (live)" run, flagging how many commits the live deploy is
behind. A deploy run with the old command (no flag) simply omits
`git_sha`; the check reports that as unverified, not as a failure.

Guardrail: the data model stays plain Postgres. No row-level security as
business logic, no edge functions, no Supabase storage in the schema, so
the database can move to any Postgres host.

## Costs

Fly: within the free allowance at this size with scale-to-zero (cold start
of a few seconds on the first request). Supabase: free tier; the project
pauses after a week without activity, which would break a demo; mitigate
with a scheduled `/healthz` ping from CI once there is a demo to protect.
GitHub Pages: free.

## Consequences

- `backend/fly.toml` is in the repo; there is no deploy workflow. After a
  backend change lands on `main`, the founder runs `cd backend && fly
  deploy`. The AI team cannot deploy (no Fly access), which matches the
  approval contract.
- CORS is configured from `FILMRUNNER_CORS_ORIGINS` (production:
  `https://sandovabarbora.github.io`).
- The Supabase connection string uses the session pooler on port 5432
  with `sslmode=require`, which works from Fly without IPv6 concerns.

## Revisit when

Manual deploys become a bottleneck (then a GitHub Actions secret with an
app-scoped, expiring Fly deploy token is the next step), cold starts annoy
a real AD (set `min_machines_running = 1`, a few
dollars a month), or the Supabase pause bites, or FR-12 picks something
other than Supabase Auth.

## Addendum 2026-09-21: crew photos in Postgres

Avatars (≤ 300 KB, resized to 256 px in the browser) are stored in a
`contact_photos` table and served by `GET /api/v1/public/contacts/{id}/photo`
with a day of cache and a version in the URL. Reason: it removes an account,
a bucket and a service-role key (which bypasses every project permission)
for a few kilobytes per person. Supabase Storage stays as an optional path
when its credentials are configured. Revisit when photos grow beyond
avatars (documents, images per scene).

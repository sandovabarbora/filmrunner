# Status

Updated: 2026-09-14 (morning brief)

## today

- 09:00 — FR-8 · tech-lead: write ADR-002 (demo hosting choice: Cloudflare Pages/GitHub Pages + Fly.io/Railway + Neon), commit deploy configs and a demo seed script, and file INBOX items for every account/domain/payment needed.
- 11:00 — FR-4 · tech-lead: write ADR-001 recording the stack restart (FastAPI + vanilla PWA over the old Next.js + Supabase), including what the old repo had that this one still lacks.
- 13:00 — FR-5 · tech-lead: write the pre-merge security/QA checklist and wire it into the PR template.
- 15:00 — FR-7 · security: fix the three founding-commit findings (hardcoded dev token default, innerHTML XSS, forgeable audit fields) with tests for each.
- 17:00 — idle: after FR-8, FR-4, FR-5 and FR-7 are claimed, no `ready` item with `gated: no`/`partial` remains (FR-1 is in-progress, FR-6 is blocked on FR-1). Only 4 of 5 shifts have work today.

## pm
- summary: FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11) — target roles (1st AD, 2nd AD, production coordinator), a 30-minute script mapped to BRIEF.md Q1-Q4/Q6, a note-taking template, sourcing/fallback channels (FAMU, Czech Film Commission, permit data), and draft invitation email text. Recruiting real candidates and sending the invitation needs the founder's own network/identity — filed as INBOX #1, pending. FR-2 teardown (docs/research/competitive-teardown.md, PR #8) still stands from the prior shift.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for external vendor domains (unchanged from the FR-2 shift); not relevant to FR-3, which needed no external fetches.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: no engineering work this shift; skeleton, CI, and routine plumbing unchanged since founding session.
- tests: 11 pytest (needs Postgres), Playwright smoke pending CI
- blockers: none
- needs_approval: no

## security (gate)
- summary: no gate run yet; checklist is FR-5 (still ready, not yet picked up). FR-7 (three founding-commit security findings: hardcoded dev token default, stored XSS via innerHTML, forgeable audit fields) is still open.
- tests: n/a
- blockers: none
- needs_approval: no

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (now done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

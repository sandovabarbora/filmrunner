# Status

Updated: 2026-09-14 15:07 (15:00 shift)

## today

Re-planned 13:55 by the founder's session after the course change (see DECISIONS.md): the working slice comes first.

- 09:00, 11:00, 13:00 — already passed (founding work in the interactive session; GitHub Pages demo shipped in PR #17).
- 15:00 — done: FR-8 seed script (PR #24). The founder's own interactive session had already delivered the rest of the planned 15:00 work (ADR-002, fly.toml, CORS-from-env, dev-token refusal — PR #22) before this shift started, so this shift picked up the remaining dod piece instead of duplicating it.
- 17:00 — FR-10 · frontend: ADR-003 for the AD editor (API calls, save points, network-loss behaviour) and the first editor.html slice if the ADR is short; plus the day summary.

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for external vendor domains.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: FR-8 — added `backend/app/seed_demo.py`, an idempotent seed script that loads one realistic demo production and call sheet through the real `create_call_sheet` service path, so the Fly/Supabase-hosted API shows real data on first open once deployed. README documents running it after `fly deploy`. PR #24 (branch `feat/fr-8-demo-seed-script`) open, CI pending. This closes another FR-8 dod bullet; still open on FR-8: the GitHub Actions deploy job (deliberately dropped per ADR-002 — manual founder-only deploy) and re-verifying the iOS Safari service-worker failure case against the Fly-hosted API. FR-8 stays in-progress.
- tests: 17 pytest (backend, run against a real local Postgres 16 this shift — all passing, up from 11: 6 new tests for the seed script, including the idempotency failure case)
- blockers: none
- needs_approval: no (the seed script only writes to a database the process can already reach; it does not create accounts, deploy, or spend money)

## security (gate)
- summary: no gate run yet; checklist is FR-5 (still ready, not yet picked up). FR-7 (three founding-commit security findings: hardcoded dev token default, stored XSS via innerHTML, forgeable audit fields) is still open.
- tests: n/a
- blockers: none
- needs_approval: no

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

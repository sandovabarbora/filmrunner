# Status

Updated: 2026-09-14 (morning brief)

## today

Re-planned 13:55 by the founder's session after the course change (see DECISIONS.md): the working slice comes first.

- 09:00, 11:00, 13:00 — already passed (founding work in the interactive session; GitHub Pages demo shipped in PR #17).
- 15:00 — FR-8 · tech-lead: ADR-002 + fly.toml + release step for alembic + CORS for the Pages origin; INBOX items for the Fly and Neon accounts. No deploy without approval.
- 17:00 — FR-10 · frontend: ADR-003 for the AD editor (API calls, save points, network-loss behaviour) and the first editor.html slice if the ADR is short; plus the day summary.

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

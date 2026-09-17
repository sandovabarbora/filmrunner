# Status

Updated: 2026-09-17 08:00 (morning brief)

## today

No backlog item qualifies for a shift today. FR-5 is the only `state: ready`
item in `BACKLOG.md`, but its entire dod already shipped in PR #59
(`docs/fr-5-pre-merge-checklist`), which is still open awaiting the
founder's merge — its dod depends on that open PR, so per the brief
contract it is skipped. Every other item is `in-progress`, `blocked`, or
`done`. FR-20 (Prague market sizing, proposed 2026-09-16 in PR #58) is not
yet `ready` in `main` either, since PR #58 is still open. Result: all five
shifts are idle unless `INBOX.md` gains an `approved` item or one of
PR #55/#58/#59 lands and unblocks a real `ready`+ungated item.

- 09:00 · idle — no qualifying backlog item
- 11:00 · idle — same
- 13:00 · idle — same
- 15:00 · idle — same
- 17:00 · idle — same; day summary sent regardless of idleness

Backlog refill: filed FR-21 (pm, switching-cost desk research, BRIEF Q6) on
`docs/backlog-proposals-2026-09-17` for the founder to merge or edit — the
ready+ungated count is otherwise 1 (FR-5), below the floor of three. PRs
#55 (`fix/alembic-merge-heads`), #58 (backlog refill, FR-20) and #59 (FR-5)
are still open and unmerged, unchanged since yesterday's 17:00 shift; no
INBOX item approves merging any of them. PR #55's CI is green on its
current head and is a real deploy blocker (two Alembic heads) — worth the
founder's merge before the next deploy.

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch`/`WebSearch` remain blocked by this session's egress proxy for most external domains (vendor pages, and confirmed earlier today for `timeanddate.com` and `api.sunrise-sunset.org`).
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: 17:00 shift — idle, nothing new to build (see `## today`); last scheduled shift of the day. Re-checked `gh pr list --state open`: still exactly #55, #58, #59, all unchanged since the 09:00/11:00/13:00/15:00 shifts; no CI or review activity on any of them today after PR #55's CI went green yesterday. Carried over from 09:00: FR-5 delivered whole in PR #59 (doc-only), awaiting founder merge. Noted for the founder, unchanged from prior shifts: PR #55 (`fix/alembic-merge-heads`, opened by an interactive session, not this routine) fixes the two-Alembic-heads deploy blocker from the 2026-09-15 13:00/15:00 shifts' parallel migrations; CI green, mergeable, still awaiting her merge (this routine cannot merge a non-state PR without an approved INBOX item naming it). PR #58 (backlog proposals, FR-20) also still open and unmerged. Carried over: FR-18's photo upload gated on INBOX #4, FR-16's push gated on INBOX #5.
- tests: n/a — no code touched this shift.
- blockers: PR #55 (migration-head fix), #58 (backlog refill), and #59 (FR-5) all unmerged; PR #55 in particular is worth doing before the next deploy.
- needs_approval: yes — INBOX #5 (VAPID keypair) and INBOX #4 (Supabase Storage bucket/secret), both carried over, both needing the founder's own credentials.

## security (gate)
- summary: FR-7 re-verified this shift and flipped from `ready` to `done`. All three founding-commit findings hold: (1) `config.py` still refuses to boot with the default bearer token outside development; (2) the original innerHTML/XSS vector is now structurally impossible — the frontend fully migrated to React and `dangerouslySetInnerHTML` is used nowhere in `frontend/src`; the original regression test is still committed but was not re-run live this shift (would need a fresh build+browser cycle; the structural fix is stronger evidence than the original bug pattern could survive under); (3) `created_by`/`published_at` audit fields are confirmed server-set from the authenticated principal in both API entry points (`_audit_label` in `app/routers/call_sheets.py`), with the one body-value fallback inside the service layer reachable only from `seed_demo.py`'s own hardcoded call, not from any HTTP input. Ran the full backend suite against a freshly created local Postgres (container is ephemeral, so filmrunner/filmrunner_test roles and DBs were recreated this shift): 88/88 pass, including all spoofed-`created_by` and dev-token tests. FR-5 (the gate checklist itself) delivered this morning by the 09:00 shift (PR #59) — see engineering above.
- tests: backend full suite 88/88 (fresh Postgres 16 this shift, no regressions since 2026-09-14's original fixes).
- blockers: none.
- needs_approval: no.

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

# Status

Updated: 2026-09-15 08:00 (morning brief)

## today

- 09:00 · FR-11 · frontend — add a QR code to the editor's publish flow so the crew link can be scanned instead of typed.
- 11:00 · FR-18 · frontend — ship the crew photo upload (gated: Supabase Storage `avatars` bucket, files an INBOX item) on top of the edit/remove flow PR #41 already delivered.
- 13:00 · FR-19 · tech-lead — add geocoding, computed sunrise/sunset, a weather suggestion, and a nearest-hospital suggestion for locations, using keyless providers per the item's own note.
- 15:00 · FR-16 · frontend — ship Web Push notifications on revision publish (VAPID keys as a Fly secret) so crew are told when a call sheet changes.
- 17:00 · FR-7 · security — verify each of the three founding-commit security fixes is actually in place and flip the item's own `state` to `done`.

No open PRs this morning, so nothing was skipped for depending on one still open. Backlog refill not needed: 3 ready+`gated: no` items (FR-11, FR-7, FR-5) still meet the floor before today's picks consume two of them.

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for external vendor domains.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: FR-9 delivered this shift (PR #42, branch `feat/fr-9-offline-honest-status`): the service worker's own cache used to answer `fetch()` when offline, which loader.ts read as "Live" because it only checked `resp.ok`. A workbox plugin in vite.config.ts now stamps every runtime-cached API response with where it came from (network vs. this worker's cache); loader.ts trusts the stamp. Added an "unknown freshness" state for a pre-upgrade worker that never stamped (dod's failure case), which needed one line in App.tsx beyond the loader/vite/test scope named for this shift — still clear of backend/ and frontend/src/editor/. Separately, the founder's own interactive session delivered a large slice of today's product outside the shift routine: FR-10 (editor), FR-12 (Supabase auth), FR-14 (contacts), FR-15 (roles), FR-17 (connected app), FR-13 (personal sheets), and opened FR-18/FR-19 (crew edit, location services) with FR-18 mid-flight in PR #41 (open). FR-8 (hosting) remains in-progress: deploy/seed is done (INBOX #2), the GitHub Actions deploy job stays deliberately dropped per ADR-002, and the iOS Safari service-worker check against the Fly-hosted API is still unverified.
- tests: frontend — 11/11 Playwright (`frontend/tests/test_smoke.py`) against a real build and the real generated service worker, up from 9: 2 new for FR-9 (cached-with-timestamp after going offline; unknown-freshness with a stub pre-upgrade worker). Backend suite unchanged this shift (17 pytest per the 15:00 shift's run).
- blockers: none
- needs_approval: no

## security (gate)
- summary: no gate run yet; checklist is FR-5 (still ready, not yet picked up). FR-7's three dod bullets are each individually marked done in BACKLOG.md (delivered piecemeal in other PRs), but the item's own `state:` was never flipped from `ready` — worth a future shift closing that out explicitly rather than leaving it looking outstanding.
- tests: n/a
- blockers: none
- needs_approval: no

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

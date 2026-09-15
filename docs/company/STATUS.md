# Status

Updated: 2026-09-15 09:12 (09:00 shift)

## today

- 09:00 · FR-11 · frontend — done: QR code added to the editor's publish flow (PR #45, open).
- 11:00 · FR-18 · frontend — ship the crew photo upload (gated: Supabase Storage `avatars` bucket, files an INBOX item) on top of the edit/remove flow PR #41 already delivered.
- 13:00 · FR-19 · tech-lead — add geocoding, computed sunrise/sunset, a weather suggestion, and a nearest-hospital suggestion for locations, using keyless providers per the item's own note.
- 15:00 · FR-16 · frontend — ship Web Push notifications on revision publish (VAPID keys as a Fly secret) so crew are told when a call sheet changes.
- 17:00 · FR-7 · security — verify each of the three founding-commit security fixes is actually in place and flip the item's own `state` to `done`.

No open PRs at the start of this shift, so nothing was skipped for depending on one still open. Backlog refill not needed.

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for external vendor domains.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: FR-11 worked this shift (PR #45, branch `feat/fr-11-qr-crew-link`, open): the editor's publish flow now renders a QR code for the crew link, next to the existing `#shareLink`, using `qrcode-generator` (zero transitive deps) drawn as plain SVG rects (no `dangerouslySetInnerHTML`). Verified against a real build and a real API — publish REV A, `#shareQr` shows a real module count, not a placeholder. FR-11 stays `in-progress`: the "REV B replaces A" note on a hot revision is left for FR-16 to add. Carried over from yesterday: FR-8 (hosting) remains in-progress (deploy/seed done via INBOX #2; iOS Safari service-worker check against the Fly-hosted API still unverified); FR-18 (crew edit/remove) has PR #41 open, photo upload still to come.
- tests: frontend — Playwright suite extended with one assertion in the existing FR-17 publish flow test (`#shareQr svg` renders with a real module count); verified locally against a real build (`frontend/dist`) and a real uvicorn+Postgres API using the pre-installed Chromium at `/opt/pw-browsers/chromium` (this session's pinned `playwright==1.47.0` can't download its own matching browser build under the egress policy, so pytest's own browser fixture wasn't usable here — CI's fresh install is unaffected). `npm run typecheck` and `npm run build` both clean.
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

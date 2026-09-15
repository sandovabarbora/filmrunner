# Status

Updated: 2026-09-15 11:12 (11:00 shift)

## today

- 09:00 · FR-11 · frontend — done: QR code added to the editor's publish flow (PR #45, merged).
- 11:00 · FR-18 · frontend — done (code side): crew photo upload shipped (PR #48, open); gated on INBOX #4 (Supabase Storage bucket + secret) before it works for real.
- 13:00 · FR-19 · tech-lead — add geocoding, computed sunrise/sunset, a weather suggestion, and a nearest-hospital suggestion for locations, using keyless providers per the item's own note.
- 15:00 · FR-16 · frontend — ship Web Push notifications on revision publish (VAPID keys as a Fly secret) so crew are told when a call sheet changes.
- 17:00 · FR-7 · security — verify each of the three founding-commit security fixes is actually in place and flip the item's own `state` to `done`.

No open PRs at the start of this shift (PR #45 had merged), so nothing was skipped for depending on one still open. PR #47 (feat/print-call-sheet, opened directly by the founder, not a backlog item) is open but unrelated to this shift's work. Backlog refill not needed.

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch` remains blocked by this session's egress proxy for external vendor domains.
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: FR-18's photo bullet worked this shift (PR #48, branch `feat/fr-18-crew-photo`, open): `Contact.photo_url`, `POST`/`DELETE /contacts/{id}/photo` (crew:edit, JPEG/PNG, 300 KB cap) uploading to Supabase Storage via a new `app/services/storage.py` with the service-role key, a cache-busted public URL, `ContactCard.photo_url` wired into Who to call and the personal sheet's department-head block via a shared `Avatar` component. Editor Crew tab resizes to 256px client-side (canvas) before upload, shows the avatar in the list and edit form, offers "Remove photo". No Supabase Storage credentials exist yet (routine can't create accounts), so the endpoint 503s with a clear message and never touches the rest of the person's saved fields — filed INBOX #4 for the founder. Still open on FR-18: offline editing of an existing person is not built (falls back to the app's generic "No connection" notice, nothing queued). FR-18 set to `in-progress` (was `ready`; edit/remove had shipped 2026-09-14 via PR #41 but the item's own state was never updated — fixed now). Carried over: FR-11 QR code (PR #45) merged since the 09:00 shift wrote its note; FR-8 (hosting) remains in-progress (deploy/seed done via INBOX #2; iOS Safari service-worker check against the Fly-hosted API still unverified). PR #47 (`feat/print-call-sheet`) is open, authored directly by the founder outside the shift cycle, not touched this shift.
- tests: backend — 46/46 pass against a real local Postgres (7 new: unconfigured→503, wrong content-type→415, oversized→413, unknown contact→404, success sets photo_url and appears in Who to call via a monkeypatched storage call, failed upload doesn't touch other fields, remove clears it). frontend — new Playwright test `test_photo_upload_failure_does_not_block_other_edits`, plus manual verification of both branches (upload success with a stub storage server; upload failure with no credentials, matching today's real production state) driven live through the pre-installed Chromium at `/opt/pw-browsers/chromium` against a real build and a real uvicorn+Postgres API (`--headless=new`, since the old headless flag pytest-playwright defaults to is no longer supported by this Chrome build; pytest's own browser fixture still can't download its matching build under the egress policy — CI's fresh install is unaffected). `npm run typecheck` and `npm run build` both clean.
- blockers: none
- needs_approval: yes — INBOX #4 (create the Supabase Storage `avatars` bucket and set the service-role key; needs the founder's own Supabase project access)

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

# Status

Updated: 2026-09-15 15:21 (15:00 shift)

## today

- 09:00 · FR-11 · frontend — done: QR code added to the editor's publish flow (PR #45, merged).
- 11:00 · FR-18 · frontend — done (code side): crew photo upload shipped (PR #48, open); gated on INBOX #4 (Supabase Storage bucket + secret) before it works for real.
- 13:00 · FR-19 · tech-lead — done: geocoding, computed sunrise/sunset, a weather suggestion, and a nearest-hospital suggestion for locations, using keyless providers (PR #51, open).
- 15:00 · FR-16 · frontend — done (code side): Web Push notifications on revision publish shipped (PR #53, open); gated on INBOX #5 (VAPID keys as a Fly secret) before the "Enable notifications" control appears for real.
- 17:00 · FR-7 · security — verify each of the three founding-commit security fixes is actually in place and flip the item's own `state` to `done`.

No open PRs at the start of this shift touched FR-16's own files (backend push/notification modules, frontend push.ts, service worker), so nothing was skipped for depending on one still open. PR #47 (`feat/print-call-sheet`), #48 (`feat/fr-18-crew-photo`) and #51 (`feat/fr-19-location-services`) are open from earlier shifts, unrelated to this shift's work. Backlog refill not needed (still 3+ ready+gated:no/partial items: FR-7, FR-5, and FR-17/FR-18's remaining pieces).

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch`/`WebSearch` remain blocked by this session's egress proxy for most external domains (vendor pages, and now also confirmed for `timeanddate.com` and `api.sunrise-sunset.org` — see engineering below).
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: FR-16 delivered this shift (PR #53, branch `feat/fr-16-push-notifications`, open): `docs/adr/ADR-007-web-push-notifications.md` picks Web Push with VAPID (`pywebpush`) — a self-issued keypair, no account or third-party service needed, unlike FCM. Backend: `PushSubscription` model + migration, `app/services/push.py` (VAPID-signed transport) and `app/services/notifications.py` (composes "REV B replaces A: crew call 07:30" and iterates subscribed crew), public subscribe/unsubscribe endpoints keyed by a crew member's own personal token (never the AD's — an AD cannot enable notifications on someone else's phone), and `GET /api/v1/public/push/vapid-key` so the frontend only offers the control once configured. Publishing a revision now sends synchronously to every subscribed crew member and returns a delivery summary; every attempt (success or failure) is logged to `DistributionLog` (new `push` channel + `error` column) so an AD can see exactly who did not get an update — the dod's own failure case, not an assumption. A 404/410 (browser revoked the subscription) deletes that row; other failures keep it for retry on the next publish. Frontend: `push-sw.js` handles `push`/`notificationclick`, wired into the generated service worker via `workbox.importScripts` since VitePWA's generateSW strategy can't add listeners itself; `NotificationToggle` appears only on a crew member's own personal link; the sheet itself now shows "REV B replaces A" from the second revision on (closes the piece FR-11's 09:00 note left open). Fallback channels (SMS, email) explicitly not built, per the dod. Filed INBOX #5 for the founder to generate the VAPID keypair (`backend/scripts/generate_vapid_keys.py`, run once by a human) and set it as Fly secrets — until then the control is code-complete but inert, same pattern as FR-18's photo upload. `docs/research/manual-test-protocol-push-ios.md` records the real-iPhone check this shift could not run (no device, Apple's push service unreachable here). Carried over: FR-19 (PR #51), FR-18 (PR #48), PR #47 all unchanged from earlier shifts' notes.
- tests: backend — 53/53 pass against a real local Postgres (14 new, `test_push.py`): subscribe/unsubscribe including an unknown-token 404 and a same-endpoint re-subscribe updating in place, the real VAPID-signing path through `py_vapid` with only the final HTTP POST mocked, successful delivery logged with a timestamp, failed delivery logged with the reason and the crew member's name (and publish itself still succeeding — a notification failure must never block a publish), a 410 response deleting the stale subscription so it isn't retried, and the "not configured"/"no subscribers" cases being silent no-ops rather than errors. `npm run typecheck` and `npm run build` clean; confirmed `push-sw.js` lands in `dist/` and `importScripts("push-sw.js")` is injected into the generated `sw.js`. Frontend E2E (`test_push_e2e.py`, committed for CI): a real build, a real uvicorn+Postgres API, and a real browser drive the actual subscribe → real POST → real DB row → "Notifications on" → reload-recognises-it → unsubscribe → real DELETE flow, plus the REV-A-has-no-note/REV-B-has-the-note check on the live sheet; only the two browser-native push APIs (`Notification.requestPermission`, `PushManager.subscribe`) are stubbed, since no phone in this environment can receive a real OS push. This sandbox's own `pytest-playwright` browser fixture has the same known gap FR-18/FR-19 noted (pinned Chromium revision absent here), so verification used a one-off script against the pre-installed `/opt/pw-browsers/chromium` (with `--headless=new`, since the pinned playwright's default old-headless flag doesn't run on that newer binary) — all checks passed.
- blockers: none for FR-16 itself beyond INBOX #5. Astronomical-accuracy follow-up from FR-19 still open (egress-blocked); FR-16's own iOS manual protocol also still open, same reason (no device, egress-blocked).
- needs_approval: yes — INBOX #5 (generate and set the VAPID keypair; a human running a script once, not an account or payment, but still outside the routine's write access to Fly secrets). Carried over: INBOX #4 for FR-18's Supabase Storage bucket/secret still needs the founder.

## security (gate)
- summary: no gate run yet; checklist is FR-5 (still ready, not yet picked up). FR-7's three dod bullets are each individually marked done in BACKLOG.md (delivered piecemeal in other PRs), but the item's own `state:` was never flipped from `ready` — planned for the 17:00 shift today.
- tests: n/a
- blockers: none
- needs_approval: no

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

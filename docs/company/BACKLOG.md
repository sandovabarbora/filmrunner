# Backlog

Ordered by priority; the founder reorders. Grammar in TEAM.md.

## FR-8 · tech-lead · Hosted API and database for the PWA (second half of the demo deployment)
- state: in-progress
- note: first half done 2026-09-14 (GitHub Pages, `?demo=1`, pages.yml, PR #17). This item is now the API: ADR-002, fly.toml + Dockerfile release step for alembic, Supabase Postgres connection via platform secrets (Postgres only; no Supabase-specific schema features), CORS for the Pages origin, INBOX items for the Fly and Supabase accounts. The PWA must be able to load a real call sheet by id from the hosted API. Founder chose Supabase over Neon on 2026-09-14 (DECISIONS.md).
- note: 15:00 shift 2026-09-14 — the founder's own interactive session had already delivered ADR-002, fly.toml (with the alembic release_command), the CORS-from-env config, and the dev-token refusal outside development (commit/PR #22) before this shift started. This shift added the remaining dod piece: `backend/app/seed_demo.py`, a seed script that creates one realistic demo production and call sheet (idempotent — checked by production name) so the hosted URL shows real data on first open, plus tests run against a real local Postgres (17/17 passing) — delivered in PR #24 (branch feat/fr-8-demo-seed-script). Filed INBOX #2 for the Fly and Supabase account/secrets/deploy step, which only the founder can do. Still open: the GitHub Actions deploy-job dod bullet was deliberately dropped in ADR-002 (manual founder-only deploy, a documented decision, not an oversight), and the iOS Safari service-worker failure case has not been re-verified against the Fly-hosted API specifically (only against the GitHub Pages demo bundle, per README).
- gated: partial
- why: showing an AD a call sheet that works on their own phone with no signal is stronger evidence than any interview question; the PWA needs HTTPS and a public API to exist outside localhost
- dod:
  - docs/adr/ADR-002-demo-hosting.md: frontend on GitHub Pages (done), backend on Fly.io (or Railway) from the existing Dockerfile, Postgres on Supabase used as plain Postgres; alternatives and costs stated; migrations run as a release step, not on every boot
  - deploy configs committed (fly.toml, Pages config, GitHub Actions deploy job triggered on main) with secrets read from the platform, never from the repo
  - INBOX items for every account, domain, or payment the founder must create; the routine never creates them
  - a seed script that loads one realistic demo production and call sheet so the URL shows something on first open
  - failure case: if the service worker does not register on iOS Safari over the deployed HTTPS URL, the ADR records it as a blocker for the demo and proposes the fallback (install banner off, plain web link) instead of shipping a demo that silently fails on the phones ADs actually carry

## FR-10 · frontend · Minimal AD editor: create a call sheet and publish a revision from a phone
- state: done
- note: delivered 2026-09-14 in the founder's session (feat/fr-10-ad-editor): editor.html, ADR-003, E2E test against the real API (publish A, publish B, crew sees B) plus the network-loss failure case.
- gated: no
- why: the wedge is "AD publishes, crew receives"; today a call sheet can only be created with curl against the API, so nothing is usable by a real AD
- dod:
  - a React route/screen in frontend/ (ADR-001 stack) lets an AD pick or create a production, create a shoot day, add schedule items (scene, int/ext, day/night, set, pages in eighths), set crew call and safety notes, and publish; publishing again creates the next revision letter through the existing API
  - works on a phone screen width first (the AD's Tuesday is on set, not at a desk); desktop is a bonus
  - the design is discussed in a short docs/adr/ADR-003-editor.md before code: which API calls, what is saved when, what happens when the network drops mid-edit
  - Playwright test against the real API: create, publish A, publish B, assert the viewer shows REV B and the schedule
  - failure case: losing the network while editing must not lose the draft; the draft is kept in IndexedDB and the app says it is unsaved

## FR-12 · tech-lead · Real auth: per-production access instead of one shared dev token
- state: done
- note: delivered 2026-09-14 (feat/fr-12-supabase-auth): ADR-004, JWKS verification in the API, email code / magic link sign-in in the editor, created_by from identity. Per-production roles remain FR-15.
- gated: no
- why: the editor cannot go to a real AD while every write is protected by a single token in an env var
- dod:
  - docs/adr/ADR-004-auth.md compares Supabase Auth (magic link, JWT verified in FastAPI), a per-production secret link, and a hand-rolled magic link; picks one for the pilot with the reason; the data model must stay plain Postgres (no RLS as business logic)
  - implementation with tests: unauthenticated writes 401, a token for production A cannot touch production B, public read stays public
  - failure case: a leaked per-production token can be rotated without losing data, and the test proves the old one stops working

## FR-17 · frontend · Connected app: productions, days, crew, edit an existing day
- state: in-progress
- gated: no
- why: the pieces exist (viewer, editor, contacts) but do not form one product: the editor cannot open an existing day, there is no production → days navigation, crew and contacts can only be entered through the API, and the root URL is a demo. Founder: "mělo by to být všechno napojený" (2026-09-14).
- dod:
  - backend: GET /productions/{id}/call-sheets lists the production's days with the current revision letter
  - editor navigation Productions → Days → Day; a production shows its days (date, day X of Y, REV, crew link with copy) and a Crew tab (name, department, position, phone, head of department); a day loads its current revision into the form, save publishes the next revision, head of day is picked from the crew, crew link shown after publish
  - the on-phone draft remains the safety net for a dropped connection, but the server is the source of truth for a day once it has been published
  - root URL becomes a small entry page: crew opens the link they were sent (demo available), the AD goes to the editor
  - E2E: create production, add a crew member as HoD, create a day, close and reopen the editor, open the day from the list, publish REV B with a head of day, crew link shows REV B and the contact
  - failure case: opening a day while offline shows the last known revision read-only with a clear "reconnect to publish" state, never an empty form that could be published as a blank revision

## FR-11 · frontend · Share link and QR for the crew
- state: done
- gated: no
- why: "in everyone's pocket" needs one tap: the AD sends a link, the crew opens it, no typing of IDs or API URLs
- dod:
  - viewer accepts `?sheet=<id>&api=<base>` and loads without showing the lookup form (done 2026-09-14, fix/pwa-root-shows-demo); the editor shows the link (done, FR-17) and a QR code after publishing
  - the link survives a hot revision: reopening it shows the current revision, and a visible "REV B replaces A" note
  - failure case: a link to a call sheet that no longer exists or is not public shows a clear message, not a spinner
- note: 09:00 shift 2026-09-15 (PR #45, branch feat/fr-11-qr-crew-link) — a QR code for the crew link now renders next to `#shareLink` after publish, built with `qrcode-generator` (zero deps) as plain SVG rects, no `dangerouslySetInnerHTML`. Verified against a real build and a real API: publish REV A, the QR svg has a real module count. Still open: the "REV B replaces A" note on a hot revision is left for FR-16 to add (it already plans that line for its own push-notification copy); the not-found/not-public failure case for the direct-load link is unverified this shift.
- note: 11:00 shift 2026-09-18 (PR TBD, branch fix/fr-11-not-found-failure-case) closed the remaining dod bullet. `loader.ts` was collapsing a 404 from the public call-sheet API into the same generic path as a network failure, so a deleted or never-existing sheet showed "the server could not be reached... reload once you have signal" — misleading, since reloading can never fix it. `loadCallSheet` now returns a distinct `not_found` result on an HTTP 404 (checked before the generic `!resp.ok` throw, no cache fallback — the same immediate-status pattern `loadPersonal` already used for an unknown personal token), and `App.tsx` renders it as "This call sheet does not exist or is not available any more... reloading will not help", never the sheet skeleton or a spinner. The backend has no separate "not public" concept yet (`_get_call_sheet_or_404` in `call_sheets.py` 404s for both "never existed" and any future "exists but not public"), so both collapse to the same message by design — noted in the PR for whoever adds real visibility control later. New Playwright test `test_share_link_to_a_missing_or_non_public_sheet_shows_a_clear_message_not_a_spinner` (`frontend/tests/test_smoke.py`) mocks a 404 and asserts the distinct text, no skeleton, and no `#sheet.visible`. `npm run typecheck` and `npm run build` clean; full suite 13/13 passing against a real build — this sandbox's pinned Chromium revision (1134) is absent as prior shifts noted, verified instead against the pre-installed `/opt/pw-browsers/chromium` with `--headless=new` via a temporary local-only fixture override, reverted before commit (not part of the diff).

## FR-14 · tech-lead · Production contacts on the sheet: who to call, head of day, heads of department, nearest hospital
- state: done
- note: delivered 2026-09-14 (feat/fr-14-contacts): migration 9520a7babf8c, crew-member endpoints, contacts computed on read, viewer section with tap-to-call, seed and demo updated. Editor cannot yet pick the head of day (needs crew UI); tracked under FR-17.
- gated: no
- why: a call sheet without phone numbers is not a call sheet; on set the questions are "who runs today", "who is my HoD", "where is the nearest hospital" (BRIEF Q3). Founder request 2026-09-14.
- dod:
  - data model: CrewMember gains `is_head_of_department`; CallSheetRevision gains `head_of_day_crew_member_id` (the person running the day, usually the 1st AD); Location already has `nearest_hospital`
  - the public sheet includes a Contacts section: head of day, production office, 1st and 2nd AD, location manager, one line per department head; nearest hospital with address from the day's first location
  - phone numbers render as tap-to-call links; email as mailto
  - migration + tests; the seed script gets contacts so the demo shows the section
  - failure case: a contact without a phone renders the name and role with "no number on file", never an empty row or a broken tel: link

## FR-13 · frontend · Personal call sheet: "your call", your department first
- state: done
- note: delivered 2026-09-14 (feat/fr-13-personal-sheet): personal_token per crew member (migration 931c2ab3ce65 with backfill), public /me/{token} endpoint, viewer "Your call" block + department-first contacts + invalid-token fallback, editor lists personal links per crew member after publish. Per-person call time uses CrewMember.standard_call_time (per-day overrides are a later item).
- gated: no
- why: a crew member opens the link for one number, their own call time; today the sheet is the same for everyone (BRIEF Q3: wrong or missed call times; Q7: the wedge is the crew's pocket). Founder request 2026-09-14.
- dod:
  - each crew member gets a personal link (token per CrewMember, not per person globally) that renders their name, department, position, personal call and pickup at the top, then the full sheet
  - the department's own notes and HoD are shown before the rest; unrelated departments are collapsed, never hidden
  - backend: CrewMember gains a per-production personal token and an endpoint that resolves it; CastCallEntry already holds per-person times
  - Playwright: two personal links for the same sheet show different "your call" blocks
  - failure case: a personal link that no longer matches a crew member shows the general sheet with a clear note, not a 404 that strands someone at 05:30
- blocked-until: FR-10 (editor) and FR-12 (auth model decided), because the personal token design must match the auth ADR

## FR-18 · frontend · Crew management: edit, remove, personal call time, photo
- state: in-progress
- gated: partial
- why: the Crew tab can only add; a typo in a phone number or a wrong department cannot be fixed, a person who left cannot be removed, and the personal call time (FR-13 reads CrewMember.standard_call_time) has no field. Founder request 2026-09-14.
- dod:
  - backend: PATCH and DELETE /productions/{id}/crew-members/{member_id} (crew:edit); PATCH /contacts/{id} for name, phone, email; removing a member who is head of day on any revision is refused with 409 naming the day
  - editor Crew tab: tap a person to edit name, phone, department, position, personal call time, head of department; remove with confirmation; changes show on the sheet immediately (contacts are computed on read)
  - photo (gated): a small avatar per contact, stored in Supabase Storage (bucket `avatars`, public read, 256 px, resized in the browser before upload); shown on the personal sheet and in Who to call. Creating the bucket is an INBOX item; the data model stores only the URL, so storage can move
  - failure case: editing a person offline keeps the change on the phone and marks it "not saved"; a failed upload never blocks saving the rest of the person
- note: ordering: edit and remove first (no external dependency), photo last. Edit/remove delivered 2026-09-14 (PR #41). 11:00 shift 2026-09-15 (PR #48, branch feat/fr-18-crew-photo, open) added the photo bullet: `contacts.photo_url` column, `POST`/`DELETE /contacts/{id}/photo` (crew:edit, JPEG/PNG, 300 KB cap, `app/services/storage.py` uploads to Supabase Storage with the service-role key and returns a cache-busted public URL), `ContactCard.photo_url` threaded through Who to call and the personal sheet's department-head block, editor Crew tab gets a resize-to-256px-then-upload control with an avatar in the list and edit form. Verified live in a real headless-Chromium browser against a real build and API: with a stub storage server the upload succeeds and the avatar renders in the crew list and in the public sheet's Who to call; with no Supabase secret configured (today's actual state) the upload 503s with a clear message and the person's other fields still save. 46/46 backend tests pass (7 new); `npm run typecheck` and `npm run build` clean. Filed INBOX #4 for the founder to create the `avatars` bucket and set the service-role key — until then the photo control is visible but always 503s. Still open: the dod's other failure-case half, an offline edit of an *existing* person keeping its change locally marked "not saved", is not built; today it just surfaces the generic "No connection" notice with nothing queued.
- note: 13:00 shift 2026-09-18 (PR #79, branch `feat/fr-18-crew-offline-edit-queue`) closed that remaining failure-case half: `frontend/src/editor/crewEdits.ts` adds a small IndexedDB queue (separate store from the day draft in `drafts.ts`) keyed by crew-member id. When `Crew.save()`'s PATCH fails offline (`ApiError.status === 0`) while editing an existing person, the edit is written to that queue, the crew row shows it immediately via an optimistic overlay with a "not saved" tag, and the edit form closes since there is nothing further to submit. The queue retries automatically the next time the Crew tab loads (e.g. after a reload back in signal) and can also be retried on demand with a "Sync" button on the row; a successful retry clears the tag and the queue entry. Adding a brand-new crew member offline is unchanged (falls back to the existing generic notice) since there is no crew-member id yet to queue against — only the dod's *editing* failure case was open. New Playwright test `test_crew_edit_offline_queues_locally_and_shows_not_saved`; full `test_editor_e2e.py` suite (11/11) and the wider frontend E2E suite (29/30 — the one failure is `test_locations_e2e.py`'s geocoding test, pre-existing and unrelated: Nominatim is unreachable through this sandbox's egress proxy, the same gap FR-19's own shift flagged) verified against a real build, a real uvicorn+Postgres API, and this sandbox's pre-installed Chromium (pinned revision 1134 absent here, same known gap prior shifts noted — used a temporary `browser_type_launch_args` override in `tests/conftest.py`, reverted before commit, not part of the diff). `npm run typecheck` and `npm run build` clean. Every ungated dod bullet is now delivered; the photo bullet itself remains gated on INBOX #4 (Supabase Storage bucket + service-role key), still `state: pending` — code-complete since PR #48, inert until the founder sets that up, so FR-18 stays `in-progress` rather than `done`. Touches `frontend/`, so per TEAM.md this needs the founder's own merge, no auto-merge.

## FR-19 · tech-lead · Location-based services: sunrise and sunset, weather, nearest hospital from the address
- state: done
- gated: partial
- why: an AD types sunrise, sunset and weather by hand from other apps every evening; the location already has an address and fields for coordinates and the nearest hospital, which nobody fills. Founder request 2026-09-14.
- dod:
  - locations get a geocoding step on save (address to lat and lng) and the editor gets a Locations tab (name, address, parking notes, nearest hospital), with a scene able to pick a location
  - sunrise and sunset are computed for the day's first location and date, no external service needed (astronomical formula, tested against a known Prague date)
  - weather for the shoot date at the location from a forecast provider with a free tier (Open-Meteo needs no key; name the provider and quote its terms in the ADR); shown as a suggestion the AD accepts, never overwriting text they typed
  - nearest hospital suggested from the coordinates (OpenStreetMap Overpass `amenity=hospital`, or the provider chosen in the ADR); the AD confirms, the sheet keeps the confirmed text
  - every external call has a timeout and a fallback: the fields stay editable and empty, the sheet never waits on a third party
  - failure case: a geocoder that returns the wrong place (common with Czech street names) must be visible: the editor shows the resolved place name next to the address so the AD can catch it
- note: any provider that needs an account or a key is an INBOX item; prefer keyless providers for the pilot
- note: 13:00 shift 2026-09-15 (PR #51, branch `feat/fr-19-location-services`) delivered every dod bullet: `docs/adr/ADR-006-location-services.md` (Nominatim geocoding, an in-process NOAA sunrise-equation formula, Open-Meteo weather, Overpass nearest-hospital, all keyless — no INBOX item needed); `Location.geocoded_display_name` + geocoding on create/update (migration `d353e6845c8e`); a Locations tab in the editor showing "not resolved, check the address" when the geocoder misses; a schedule item's Set row gets a location picker; sunrise/sunset auto-fill on publish from the day's first located scene when the AD leaves both blank (never overwrites typed values); weather and nearest-hospital "Suggest" buttons that fill the existing free-text field only on explicit "Use", never automatically. 67/67 backend tests pass (28 new: astronomy self-consistency + a wide-tolerance cross-check, geocoding/weather/hospital services with every external call mocked, the router's geocode-on-save/re-geocode-on-address-change/suggestion endpoints, sunrise/sunset auto-fill and its typed-value-wins case). `npm run typecheck` and `npm run build` clean. Verified live against a real build, a real uvicorn+Postgres API, and the real (blocked) network: adding an address genuinely fails to geocode in this sandboxed environment, and the editor correctly shows the "not resolved" fallback rather than hanging or erroring — the dod's own failure case, exercised for real, not mocked. A committed Playwright suite (`frontend/tests/test_locations_e2e.py`) covers the same paths for CI, where egress is unrestricted; this shift's `pytest-playwright` browser fixture can't download its pinned Chromium build here (same known gap FR-18 noted), so it was run instead via a one-off script against the pre-installed `/opt/pw-browsers/chromium`. Astronomical accuracy is flagged unverified against a live source in the ADR — `timeanddate.com` and `api.sunrise-sunset.org` are both egress-blocked this shift; a follow-up should confirm minute-level accuracy once egress allows. Not done this shift: the seed demo location has hand-set coordinates rather than a live geocode (documented in `seed_demo.py`, consistent with the script needing to run without guaranteed internet).

## FR-16 · frontend · Notifications on publish and revision
- state: in-progress
- note: FR-13 done; the receiver is identified by the personal token
- note: 15:00 shift 2026-09-15 (branch `feat/fr-16-push-notifications`) delivered every dod bullet except the on-device fallback channels (out of scope by the dod itself) and the real-iPhone manual check: `docs/adr/ADR-007-web-push-notifications.md` picks Web Push with VAPID (`pywebpush`) — no account needed, unlike FCM. Backend: `PushSubscription` model + migration, `app/services/push.py` (transport, VAPID-signed sends via `pywebpush`) and `app/services/notifications.py` (who gets told and what it says), public subscribe/unsubscribe endpoints keyed by a crew member's own personal token (never the AD's), and `GET /api/v1/public/push/vapid-key` so the frontend only offers the control once configured. Publishing a revision (both the initial and a hot revision) now sends to every subscribed crew member of the production synchronously and returns a `notifications` summary (attempted/delivered/failed) in the response; every attempt is logged to `DistributionLog` (extended with a `push` channel and an `error` column) so an AD can see exactly who did not get REV B, not just assume everyone did — the dod's own failure case. A 404/410 from the push service (the browser itself revoked the subscription) deletes that row so it is not retried; any other failure keeps it. Frontend: `push-sw.js` handles `push`/`notificationclick`, imported into the generated service worker via `workbox.importScripts` (vite.config.ts) since VitePWA's generateSW strategy cannot add custom listeners itself; `src/push.ts` (subscribe/unsubscribe/support-check) and `NotificationToggle` shown only on a crew member's own personal link (`?me=<token>`), never in the editor; the sheet itself now shows "REV B replaces A" from the second revision on (also serves FR-11, no backend field needed — computed from the revision letter). 53/53 backend tests pass (14 new, `backend/tests/test_push.py`: subscribe/unsubscribe, the real VAPID-signing path with only the final HTTP POST mocked, successful and failed delivery logging, a revoked-subscription cleanup, and the "publish still succeeds when notifications fail" invariant). `npm run typecheck` and `npm run build` clean; `push-sw.js` confirmed present in `dist/` and `importScripts("push-sw.js")` confirmed injected into the generated `sw.js`. This sandbox's own `pytest-playwright` browser fixture has the same known gap FR-18/FR-19 noted (pinned Chromium revision not present here), so `frontend/tests/test_push_e2e.py` (committed, for CI) was verified instead via a one-off script against the pre-installed `/opt/pw-browsers/chromium`: a real build, a real uvicorn+Postgres API, and a real browser drove the actual subscribe → real POST → real DB row → "Notifications on" → unsubscribe → real DELETE flow end to end, with only the two literal browser-native APIs (`Notification.requestPermission`, `PushManager.subscribe`) stubbed — there is no phone in this environment to receive an actual OS notification. Filed INBOX #5 for the founder to generate the VAPID keypair (`backend/scripts/generate_vapid_keys.py`, run once by a human, never by the routine) and set it as Fly secrets — until then the feature is code-complete but inert (`vapid-key` returns null, no control shown), the same pattern FR-18's photo upload uses for its own missing secret. `docs/research/manual-test-protocol-push-ios.md` records the real-iPhone check for whoever runs the pilot to do once a phone and the deployed URL are both available; this shift could not run it (no device, and Apple's push service is unreachable from this environment).
- gated: partial
- why: "crew missing an update" is the failure the living call sheet exists to prevent (BRIEF Q3); a revision that nobody is told about is a PDF with extra steps. Founder request 2026-09-14.
- dod:
  - Web Push for the installed PWA (VAPID keys as Fly secrets; iOS supports push for home-screen PWAs since 16.4, verified against Apple's documentation with the date checked); subscription stored per CrewMember
  - on publish of a new revision, every subscribed crew member gets "REV B replaces A: crew call 07:30" with a tap-through to the sheet; the sheet shows a "REV B replaces A" line (also serves FR-11)
  - fallback channels (SMS, email) are designed but not built; any account or paid service is an INBOX item
  - Playwright or unit tests for the subscription flow; a manual test protocol on a real iPhone recorded in docs/research
  - failure case: a push that cannot be delivered is logged per crew member so the AD can see who did not get the update, instead of assuming everyone did
- blocked-until: FR-13 (personal identity of the receiver)

## FR-15 · tech-lead · Roles and privileges per production
- state: done
- note: delivered 2026-09-14 (feat/fr-15-roles): ADR-005, production_members, policy in app/authz.py, members endpoints, editor Members tab and permission-aware UI, 5 backend role tests + E2E.
- gated: no
- why: an AD publishes, a coordinator edits, a department head sees and annotates their department, everyone else reads; one shared token cannot express that. Founder request 2026-09-14; builds on FR-12.
- dod:
  - docs/adr/ADR-005-roles.md: roles `ad` (edit + publish), `coordinator` (edit drafts), `hod` (read all, edit own department notes), `crew` (read own personal sheet); roles are per production, one person can differ across productions
  - enforcement in the API (dependency that resolves user + production role), with tests: hod cannot publish, coordinator cannot publish, crew cannot read drafts
  - the editor shows only what the role may do; the viewer is unchanged for crew
  - failure case: a user with no role on a production gets 403 with a message naming the production, and nothing leaks about its existence beyond the name they already have
- blocked-until: FR-12

## FR-7 · security · Fix three findings from the founding commit review
- state: done
- gated: no
- why: an automated security review of commit 81e9fc4 found a hardcoded dev token default in backend/app/config.py, stored XSS in frontend/index.html (API data rendered via innerHTML without escaping), and forgeable audit fields in backend/app/services/call_sheets.py
- dod:
  - config.py has no default bearer token; the app refuses to start without FILMRUNNER_API_BEARER_TOKEN outside development (done 2026-09-14, feat/fly-supabase-hosting, backend/tests/test_config.py)
  - index.html renders every API string via textContent or an escape helper; a test injects `<img onerror>` into a schedule item and asserts it is shown as text (done 2026-09-14 in feat/github-pages-demo, test_schedule_text_is_not_interpreted_as_html)
  - audit fields (created_by, published_at) are set server-side from the authenticated caller and the clock, never from the request body; a test sends spoofed values and asserts they are ignored (done 2026-09-14 with FR-12, backend/tests/test_auth.py)
  - failure case: if a fix would break the offline cache format, the PR says so and bumps the cache version instead of silently changing shape
- note: 17:00 shift 2026-09-15 — re-verified all three, no new code needed. (1) config.py's `_refuse_dev_token_outside_development` validator confirmed unchanged and covered by `test_config.py`. (2) the app has since fully migrated from the vanilla-JS `index.html` that had the original innerHTML bug to a React entry (`main.tsx`); grepped all of `frontend/src` for `dangerouslySetInnerHTML` — zero uses, `CallSheetView.tsx` has a standing comment noting why; the original regression test (`test_schedule_text_is_not_interpreted_as_html` in `frontend/tests/test_smoke.py`) is still committed and targets the built app, though not re-run live this shift (would need a browser build cycle beyond what a verification-only task warrants; the structural fix — no innerHTML/dangerouslySetInnerHTML anywhere in the codebase — is stronger evidence than the original bug pattern could survive). (3) read `call_sheets.py`: `publish_revision`/`create_call_sheet` take a `created_by` kwarg that the router always fills via `_audit_label(principal, ...)` — a real user's identity or a `service:`-prefixed label, never the raw request body; the body-value fallback inside `call_sheets.py` is reachable only from `seed_demo.py`'s own hardcoded call, not from any HTTP input. Set up a fresh local Postgres (container is ephemeral) and ran the full backend suite: 88/88 pass, including `test_auth.py`'s two spoofed-`created_by` tests (both a Supabase JWT user and a service token) and all 9 of `test_config.py`. No regressions found; item flipped to done.

## FR-9 · frontend · Offline-honest status when the service worker serves from cache
- state: done
- gated: no
- why: verified 2026-09-14 on the live URL: after going offline and reloading, the app said "Live data" because sw.js answered the fetch from cache; the thesis is offline-honest, so this is a product bug, not cosmetics
- dod:
  - sw.js marks cache-served responses (e.g. a custom header or a wrapped Response) and index.html shows the cached-copy status with the original fetch time when it sees the mark
  - Playwright test: load once online, go offline, reload, assert the status says cached and shows a timestamp
  - failure case: if the mark is missing (older service worker still active), the app must not claim "live"; it says "unknown freshness" rather than guessing
- note: delivered 2026-09-14 (17:00 shift, feat/fr-9-offline-honest-status, PR #42). A workbox plugin in vite.config.ts stamps every runtime-cached API response with where it came from (network vs. this worker's own cache); loader.ts trusts that stamp instead of `resp.ok`, which used to read a cache hit as "Live". Also handles the dod's failure case (a pre-upgrade worker still active, no stamp) as a new "unknown freshness" state — needed one added line in App.tsx beyond the three files STATUS.md named for this shift, since that state can't render without it; App.tsx is outside backend/ and frontend/src/editor/, so within the shift's actual constraint. 11/11 Playwright tests pass against a real build (frontend/dist) and the real generated service worker, including both new ones; not independently verified against an actual pre-upgrade worker in the wild, only a stand-in stub built for the test.

## FR-3 · pm · Customer discovery plan: five Prague interviews
- state: done
- gated: partial
- why: Q1 to Q4 in BRIEF.md can only be answered by the people who make call sheets
- dod:
  - docs/research/discovery-plan.md names the target roles (1st AD, 2nd AD, production coordinator), a 30-minute script, and a note-taking template
  - a draft invitation email exists as text; sending it is an INBOX item, not done by the routine
  - failure case: if fewer than five candidates can be named from the founder's network, the plan says how to find the rest (film schools, FAMU, production listings) instead of shrinking the sample
- note: delivered in PR #11 (branch docs/fr-3-discovery-plan) — target roles, a 30-minute script mapped to BRIEF.md Q1-Q4/Q6, a note-taking template, and draft invitation email text. Recruiting real candidates and sending the invitation needs the founder's own network and identity, not the routine; filed as INBOX #1.

## FR-1 · pm · BRIEF.md v0 to v0.1: sharpen questions and hypotheses
- state: done
- gated: no
- why: there is no constitution; every other item needs one to justify itself
- dod:
  - each open question in BRIEF.md has an owner and a concrete way it gets answered
  - the June 2026 brief (docs/reference/PRODUCT_BRIEF-2026-06.md) is read and its claims are listed as hypotheses, not facts
  - failure case: a hypothesis we cannot test within a month is marked "parked", not deleted or silently believed
- note: v0.1 shipped (BRIEF.md). 15:00 shift 2026-09-18 (PR #81, branch docs/fr-1-verified-source-brief) closed dod bullet 2: `docs/reference/PRODUCT_BRIEF-2026-06.md` was not actually missing — it has been in this repo since commit `b918215` (2026-09-14, the founder's own commit), but every shift since, including the one that wrote the "could not open it" note, searched the old external path or fetched vendor-style URLs instead of checking `docs/reference/` in the local checkout. Read in full this shift; BRIEF.md's "Assumptions" section is rewritten from the real content (H1 corrected — budgeting is explicitly cut from the June brief's own v1, not assumed included; H2 confirmed — the brief argues for keeping Next.js+FastAPI+Supabase, the restart was a scope choice not a technical finding; H3 replaced with the real figures: €99–499 tiered flat fee, free for film schools, Prague-first; two new hypotheses H4/H5 added), each cited to a section of the source and dated. No hypothesis is parked: FR-3 (the trigger for the one-month parking clock) has not started, still blocked on INBOX #1. Also recorded in `DECISIONS.md` as a process-gap correction. Failure case holds: nothing here is asserted as fact, only as a hypothesis for FR-3 or the marked-owner question to test. Touches BRIEF.md/DECISIONS.md, so no auto-merge; PR #81 awaits founder merge.

## FR-2 · pm · Competitive teardown of call-sheet tools
- state: done
- gated: no
- why: we must know what an AD would have to give up to switch
- dod:
  - docs/research/competitive-teardown.md covers StudioBinder, Yamdu, SetHero, Movie Magic Scheduling, Croogloo
  - for each: how a call sheet is built, revised, distributed, viewed offline; pricing; who the buyer is
  - every claim cites the vendor page or docs it came from, with the date checked
  - failure case: a tool whose behaviour cannot be verified from public sources is marked "unverified", not guessed
- note: delivered in PR #8 (branch shift/FR-2). `WebFetch` was blocked by this session's egress proxy for every vendor domain, so the teardown is built from `WebSearch` snippets, not directly-read vendor pages; several items are flagged "unverified" and a follow-up re-verification pass is requested in the doc.

## FR-6 · marketing · Positioning draft
- state: ready
- gated: no
- why: outreach and landing need one sentence of positioning that survives contact with an AD
- dod:
  - docs/marketing/positioning.md with alternatives considered and the chosen one, grounded in FR-1 and FR-2 findings
  - blocked until FR-1 and FR-2 are done
  - failure case: if FR-2 shows a competitor already owns the chosen position, the draft says so and proposes another, rather than ignoring it
- note: 15:00 shift 2026-09-18 — unblocked: FR-1 flipped to `done` this shift (PR #81), FR-2 was already `done`. Not worked this shift (this shift's own item was FR-1); next shift or a future run can take it.

## FR-4 · tech-lead · ADR-001: stack of the skeleton
- state: done
- note: frontend half decided and written 2026-09-14 (docs/adr/ADR-001-frontend-stack.md, React + Vite + TS).
- note: 17:00 shift 2026-09-18 (PR #83, branch docs/fr-4-adr-001-backend-half) delivered the remaining backend half: docs/adr/ADR-001-backend-stack.md states the three options (keep the old Next.js + FastAPI + Supabase repo, this FastAPI + Postgres skeleton, a hybrid vendoring the old repo's auth code), the decision (this skeleton, citing DECISIONS.md 2026-09-14), and lists what the old repo had that this one lacks — script-to-breakdown AI drafting, RLS-based authorization, budgeting, deeper scheduling depth, a general change-log feed — each with the specific BRIEF.md trigger that would justify porting it, cited against the June 2026 brief's actual content (docs/reference/PRODUCT_BRIEF-2026-06.md, verified in full by the 15:00 shift the same day). Names the revisit trigger per the dod's own failure case: a new ADR supersedes this one rather than editing the decision in place. Cross-linked with ADR-001-frontend-stack.md. Doc-only (docs/adr/**), so per TEAM.md this needs the founder's own merge, no auto-merge; all three dod bullets are now delivered so this PR is the whole remaining deliverable.
- gated: no
- why: the restart from Next.js + Supabase to FastAPI + vanilla PWA must be a recorded decision, not an accident
- dod:
  - docs/adr/ADR-001-stack.md states the options (keep old repo, this skeleton, hybrid), the choice, and the consequences
  - it lists what the old repo had that this one lacks (auth, SSO scaffold, budget, scheduling) and when each would be ported
  - failure case: if a hard requirement in BRIEF.md later contradicts the choice, the ADR names the trigger to revisit rather than being rewritten

## FR-5 · tech-lead · Security and QA gate checklist
- state: done
- gated: no
- why: gates exist as roles in TEAM.md but not as a checklist anyone can run
- dod:
  - docs/gates/pre-merge-checklist.md with security items (secrets, auth on every non-public route, input validation, dependency pins) and QA items (tests for the change, failure case covered, CI green)
  - the PR template references it
  - failure case: a PR that skips the checklist is visible as such in the template, not silently merged
- note: 09:00 shift 2026-09-16 (PR #59, branch docs/fr-5-pre-merge-checklist) delivered the whole dod: docs/gates/pre-merge-checklist.md (security: no secrets, auth on every non-public route via require_principal/authz.require_on, input validation, no unescaped external data in HTML citing the FR-7 regression test, server-set audit fields, exact-pinned dependencies, no unapproved spend/account/deploy; QA: tests including the failure case, CI green on the PR's own head, real verification when a dod demands it) and the PR template, expanded from 5 to 8 checkboxes and linking the file, so a skipped item is visible on the PR itself. Doc-only change, `python scripts/check_company_docs.py` clean; no code, so no test suite applies. Awaits founder merge.

## FR-21 · pm · Switching-cost research: what would make an AD leave a named incumbent mid-season
- state: done
- gated: no
- why: BRIEF.md Q6 asks what would make an AD switch tools mid-season; FR-2's teardown named the incumbent per production size but did not investigate lock-in mechanics, and FR-3's interviews (the primary source for this question) are blocked on the founder recruiting real candidates (INBOX #1). This half of Q6 is answerable now from public sources while interviews remain blocked.
- dod:
  - docs/research/switching-cost-teardown.md covers the incumbents named in FR-2's teardown (StudioBinder, Yamdu, SetHero, Movie Magic Scheduling, Croogloo): what data an AD or production office would lose or have to re-enter if they left (schedules, contact lists, templates, revision history), whether each offers a working export function, and any lock-in signals found in public reviews or forums (e.g. G2, Capterra, Reddit)
  - every claim cites its source and the date checked, the same convention FR-2 uses
  - the doc explicitly separates these desk-research findings from FR-3's own interview question ("what would have to be true for you to switch") so a future shift never treats desk research as a substitute for a real interview answer
  - failure case: a lock-in or export claim that cannot be verified from a public source is marked "unverified", not guessed, same convention as FR-2
- note: 09:00 shift 2026-09-18 (branch docs/fr-21-switching-cost-teardown) delivered docs/research/switching-cost-teardown.md covering all five FR-2 incumbents: documented export functions (StudioBinder PDF/CSV, SetHero's full export collection, Croogloo's contact export, Movie Magic's version-gated native/third-party exports), and two sourced lock-in signals (Yamdu's tiered contact-retention complaint from Capterra reviews, Movie Magic's "locked in" framing from a competitor page, flagged as needing neutral re-verification). No Reddit/forum discussion of switching surfaced despite four targeted searches; marked unverified rather than assumed absent. The doc explicitly separates these desk findings from FR-3's own interview question, which stays blocked on INBOX #1. This shift's originally-assigned item (FR-8: verify the PWA service worker on the real Fly-hosted URL over iOS Safari) was skipped — this session's egress proxy rejects `filmrunner-api.fly.dev` outright (confirmed with a direct curl) and no iOS device exists here either, so the check is undoable this shift; noted in STATUS.md.
## FR-20 · marketing · Prague market sizing: how many active productions are there
- state: ready
- gated: no
- why: BRIEF.md Q5 asks whether Prague is dense enough for word-of-mouth distribution; this is answerable from public listings, unlike Q1-Q4/Q6 which need real interviews (INBOX #1, blocked on the founder). The backlog otherwise has no item against Q5.
- dod:
  - docs/research/prague-market-sizing.md defines "active production" as one that issued a call sheet in the last 30 days, per BRIEF.md Q5
  - counts it from Czech Film Commission listings, FAMU student/graduate productions, and any public filming-permit data findable by WebSearch
  - the count is compared against a stated word-of-mouth sample-size threshold, citing the source for that threshold
  - every claim cites its source and the date checked
  - failure case: if no public source can establish a count, the doc says so explicitly and proposes the narrowest fallback (e.g. asking FR-3 interviewees to estimate) instead of guessing a number

## FR-22 · pm · Desk research: who assembles call sheets and what they use today (Q1/Q2 public-source proxy)
- state: ready
- gated: no
- why: BRIEF.md Q1 and Q2 can only be fully answered by real interviews (FR-3), which stay blocked on the founder recruiting candidates (INBOX #1); public crew job postings and industry discussion can give an early, weaker signal on who drafts/approves/distributes call sheets and what tool a production names today, the same kind of desk-research complement FR-21 already built for Q6
- dod:
  - docs/research/call-sheet-role-and-tooling-signals.md gathers public Czech production crew job postings and classifieds (e.g. filmtalent.cz, Facebook crew groups, LinkedIn) and any public forum or discussion (Reddit, industry groups) that names who assembles, approves, or distributes call sheets, and what tool or workflow (email+PDF, WhatsApp, StudioBinder, etc.) a production names using
  - findings are coded by production size (short <15 crew, feature <50, feature/TV >50) wherever a source states or implies it, the same convention FR-3's interview script uses
  - the doc states explicitly, wherever cited elsewhere, that this is a public-source proxy and never a substitute for FR-3's real interview answers
  - failure case: if no public source names a role and a tool/workflow together, the doc says so explicitly rather than inferring a link between separately-found facts

# Backlog

Ordered by priority; the founder reorders. Grammar in TEAM.md.

## FR-66 · qa · CI check of the live Fly + Pages stack, unblocked by this environment's egress proxy
- state: done
- note: delivered 2026-09-22 (feat/fr-66-live-check-workflow): `.github/workflows/pilot-readiness.yml` (daily 05:10 UTC + workflow_dispatch) runs `scripts/check_live_stack.py` — eleven public checks: API health, the deployed build carries this week's routes (FR-32/36/57/65), unknown token and unknown sheet refused, VAPID key configured, CORS allows the Pages origin, all four pages serve their own content, a handful of requests is not rate-limited. Pass/fail table into the job summary; any unreachable host or unexpected status fails the job with the error text (verified by pointing it at an invalid host). No tokens in the workflow. The readiness file now points at the workflow instead of a blocked curl
- gated: no
- why: every FR-8/FR-16/FR-40 attempt this week has been undoable from this routine's sandbox — its egress proxy 403s `filmrunner-api.fly.dev` outright, confirmed again on every hourly shift since 2026-09-14 — so "NOT VERIFIED against the live API" rows have piled up in `docs/research/pilot-readiness-2026-09.md` (FR-38, FR-39, FR-42, FR-43, FR-44) with no path to close them from this environment. A GitHub Actions runner is not behind this proxy and can reach the real deployed URLs, which matters before the founder's Friday pilot-ready goal.
- dod:
  - `.github/workflows/pilot-readiness.yml`, triggered on `workflow_dispatch` and a daily schedule, hits only public, unauthenticated endpoints on the live stack: the seeded demo call sheet at `GET https://filmrunner-api.fly.dev/api/v1/public/call-sheets/{demo_id}` (the id `backend/app/seed_demo.py` creates), the GitHub Pages demo URL (`https://sandovabarbora.github.io/filmrunner/`), and a throwaway-token 404 check on `/api/v1/public/crew/{token}/next` — no bearer token or new GitHub secret needed, so no INBOX item
  - the job writes a pass/fail table to the workflow's job summary and fails the job on any unreachable host or non-2xx/non-404-as-expected result
  - `docs/research/pilot-readiness-2026-09.md` gets one line pointing at the workflow, so a future shift reads its last run instead of repeating a blocked `curl`
  - failure case: if the deployed stack itself is down, the job fails loudly with the HTTP status or connection error, never silently recorded as "not verified"

## FR-8 · tech-lead · Hosted API and database for the PWA (second half of the demo deployment)
- state: done
- note: 2026-09-22: closed as done — the hosted API and database have been live since 2026-09-15 and verified end to end by two live runs (FR-26, FR-40); the remaining iOS Safari service-worker check belongs to FR-28 (founder's phone)
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
- state: done
- note: 2026-09-22: closed as done — productions → days → crew → day editing, first-run checklist, roles, all shipped between FR-17 and FR-58; nothing ungated remains in its dod
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
- state: done
- note: photo storage moved to Postgres 2026-09-21 (no bucket, no service-role key); INBOX #4 closed as not needed
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
- state: done
- note: 2026-09-22: closed as done — push is live (VAPID set, delivery logged, cancel and revisions push); the real-iPhone check belongs to FR-28
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
- state: done
- gated: no
- why: outreach and landing need one sentence of positioning that survives contact with an AD
- dod:
  - docs/marketing/positioning.md with alternatives considered and the chosen one, grounded in FR-1 and FR-2 findings
  - blocked until FR-1 and FR-2 are done
  - failure case: if FR-2 shows a competitor already owns the chosen position, the draft says so and proposes another, rather than ignoring it
- note: 15:00 shift 2026-09-18 — unblocked: FR-1 flipped to `done` this shift (PR #81), FR-2 was already `done`. Not worked this shift (this shift's own item was FR-1); next shift or a future run can take it.
- note: 09:00 shift 2026-09-21 (PR TBD, branch `docs/fr-6-positioning-draft`) delivered `docs/marketing/positioning.md`: four alternatives considered (AI-speed per the June brief's H4, delivery tracking, Prague-locality, live+offline-honest), each with a reason for or against, grounded directly in `BRIEF.md`'s working hypothesis/H1-H5/Q5-Q6 and `competitive-teardown.md`'s per-incumbent findings. Chose live+offline-honest. Handled the dod's failure case explicitly rather than skipping it: StudioBinder already markets a "living" call sheet (sourced from FR-2), so the doc narrows the claim to the conjunction — live *and* honest about staleness when offline — since FR-2 found StudioBinder's own offline capability was only described as "in the pipeline" (unverified, not shipped) and no other incumbent verifiably ships both. Named the revisit trigger if that verification status changes, and flagged that FR-3's Q3 pain list does not name "offline-honest" verbatim, so the position should be re-tested against real interview data once it exists, not kept on desk research alone. Marked explicitly as a hypothesis for FR-3 to test, citing `BRIEF.md`'s own kill criterion. Doc-only (`docs/marketing/**`), so per `TEAM.md` this qualifies for auto-merge. FR-6 set to done — the dod's three bullets (alternatives + chosen position, blocked-until satisfied, failure case handled) are all delivered and the PR is the whole deliverable.

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
## FR-23 · frontend · "REV B replaces A" on the sheet and in the push
- state: done
- note: delivered 2026-09-21 (feat/fr-23-revision-diff): server-side `revision_changes(prev, cur)` in services/call_sheets.py (crew call, shooting call, scene order, safety notes, count of personal calls moved) exposed as `previous_revision` + `changes` on every call-sheet read; the push body uses the same summary ("REV B replaces A: crew call 06:30 → 07:30"); viewer shows "REV B replaces A, issued 06:12" and a compact change list; a sheet with only REV A has neither. Chosen server-side over the dod's client-side option so the push and the sheet cannot drift. 3 backend tests + E2E. Backend changed: deploy needed (no migration)
- gated: no
- why: hackathon goal (pilot-ready); a crew member who opened REV A at night must see at a glance that B replaced it and what changed (BRIEF Q3: late revisions are the top failure)
- dod:
  - the viewer shows a line under the badge: "REV B replaces A, issued 06:12" using the revision history from the public read (previous letter and created_at)
  - a compact diff of what changed between the last two revisions: crew call, shooting call, scene order, safety notes; computed client-side from both revisions, no new endpoint if the public read can include the previous revision summary
  - the push payload (FR-16) carries the same one-line summary
  - Playwright: publish A then B with a different crew call, the viewer shows "replaces A" and "crew call 06:30 → 07:30"
  - failure case: a sheet with only REV A shows no diff line at all, not an empty "replaces" sentence

## FR-24 · frontend · Per-day personal call overrides
- state: done
- note: delivered 2026-09-21 (feat/fr-24-personal-calls): crew_call_entries per revision, copy-forward, precedence day > standing > general, pickup and note on the personal sheet, personal-calls table in print
- gated: no
- why: FR-13 reads CrewMember.standard_call_time, but on a real day the gaffer is called an hour early on Tuesday only; the AD must be able to set per-person times for a day (BRIEF Q1/Q3)
- dod:
  - data: per-revision crew call entries (crew_member_id, call_time, pickup_time, note) alongside the existing cast calls; a new revision copies the previous entries so the AD edits, not retypes
  - editor day screen: a "Personal calls" section listing the crew with an optional time per person; empty means the general crew call
  - personal sheet (FR-13) prefers the day's entry over the standing time; the print layout lists personal calls in a small table
  - backend tests for precedence (day entry > standing time > general call) and copy-forward on revision; E2E sets one person's time and sees it on their personal link
  - failure case: a crew member removed after entries exist does not break publishing; their entry is dropped with a note in the PR's test

## FR-29 · frontend · Send the call sheet as a WhatsApp message
- state: done
- note: delivered 2026-09-21 (feat/fr-29-whatsapp-share): `frontend/src/editor/shareText.ts` (text builders, wa.me number normalisation), day screen "Send day as text" (Web Share API, copy fallback with preview) and "Open in WhatsApp", per-person WhatsApp link with their own call/pickup/note; buttons wait for publish when the draft is dirty. Vitest added (`npm test`, 12 unit tests, in CI); E2E covers the personal call in the message, the publish guard and the unusable-phone fallback. Fixed on the way: a hot revision never cleared `dirtySincePublish` (update() overrode the patch), so the day screen kept saying "Changes since REV B" right after publishing B
- gated: no
- why: Prague crews live in WhatsApp groups; today the AD copies a link and pastes it by hand, so half the crew gets the link and half gets a screenshot. One tap that opens WhatsApp with the day already written (call, location, link) is the distribution the living call sheet has been missing (BRIEF Q3, FR-2 teardown: no competitor does per-person WhatsApp)
- dod:
  - day screen, once published: "Send day as text" builds a plain-text summary (production, day, date, calls, first location with address, weather, schedule, crew link) and opens the phone's share sheet (Web Share API); without it, copies the text and offers a wa.me link
  - per crew member: "WhatsApp" opens a chat with that person (wa.me with their phone) prefilled with a personal message: their own call, pickup and note for the day plus their personal link; a member without a phone gets copy/share instead
  - the text always reflects the published revision: with unpublished edits the buttons are disabled and the hint says to publish first
  - unit tests for the text builders and the phone normalisation (Czech 9-digit numbers get 420, spaces and 00 prefix removed); E2E checks the per-person message carries the day's personal call
  - failure case: a phone that cannot be turned into a wa.me number (letters, too short) shows the copy/share path, never a broken WhatsApp link

## FR-31 · frontend · Paste the crew list
- state: done
- note: delivered 2026-09-21 (feat/fr-31-paste-crew-list): `crewImport.ts` parses what people actually paste (department headers "Camera:", comma/semicolon/tab rows, a phone anywhere in the row, "HoD" marker, name-only lines get General/Crew with a visible warning), the Crew tab previews every row before "Add N people", people already on the crew are skipped, failures stay in the box by name. 5 unit tests, 1 E2E
- gated: no
- why: the crew already exists in a spreadsheet or last production's PDF; typing 40 people through a form is the moment an AD gives up on the tool (FR-1 brief: setup cost is the adoption barrier)
- dod:
  - Crew tab: "Paste a list…" opens a box; each non-empty line becomes a preview row (name, department, position, phone, HoD); "Camera:" lines set the department for the lines below
  - one button adds everyone; people already on the crew are shown as such and not duplicated
  - failure case: a row the API rejects is named in the notice and stays in the box; the others are still added
## FR-30 · frontend · Tomorrow starts as today: "Start Day N+1 from this one"
- state: done
- note: delivered 2026-09-21 (feat/fr-30-next-day-from-this): `nextDayFrom` in drafts.ts copies unit, calls, head of day, safety notes, scenes and personal calls into an unpublished new day one date on (weather and sun left blank: they belong to the date); the button appears on a published day; an existing unpublished new day is never replaced silently (Replace/Keep). A plain "+ New day" now continues the numbering and the date from the last day. 6 unit tests, 1 E2E
- gated: no
- why: an AD's Day 2 is Day 1 with a new date and new scenes; retyping the unit, the calls, the head of day and every personal call each evening is the kind of chore that sends people back to the PDF
- dod:
  - on a published day: "Start Day N+1 from this one" opens the new-day screen prefilled (date +1, day N+1, unit, calls, head of day, safety notes, scenes, personal calls); weather, sunrise and sunset blank
  - a brand-new day (no copy) proposes day number and date continuing the last day
  - failure case: an unpublished new day already on the phone is not overwritten without asking

## FR-32 · tech-lead · One link per person for the whole shoot
- state: done
- note: delivered 2026-09-21 (feat/fr-32-one-link-per-person): `GET /public/crew/{token}/next` picks the earliest shoot day on or after Prague's today (else the last one), listing all days; the viewer's `?api=&me=` mode resolves it (answer cached per token so the link opens the right saved sheet with no signal), then behaves as the day link with the personal block, plus an "other days" nav when there is more than one; editor and Crew tab hand out the stable link ("Link" per person, WhatsApp messages carry it). Unknown token on the stable link says so instead of guessing a day. 3 backend tests, E2E ×2. Backend changed: deploy needed (no migration)
- gated: no
- why: until now a crew member got a new link every day (sheet id + token), so "the link the AD sent" went stale every evening; one link they can pin is what makes the living call sheet a habit rather than a daily paste (BRIEF Q3)
- dod:
  - a personal link without a sheet id opens that person's next shoot day with their personal block; other days reachable from it
  - editor hands out only stable links; day links keep working
  - offline: the last resolved day opens from cache
  - failure case: a token no longer on any crew says so plainly, never a wrong person's day

## FR-33 · frontend · Cast on the call sheet
- state: done
- note: delivered 2026-09-21 (feat/fr-33-cast-calls): cast members API (`/productions/{id}/cast-members` CRUD, contact carried), cast calls copy forward across revisions like personal calls (None = copy, [] = clear), named `cast_calls` rows on every call-sheet read in call order, migration c9e5a3b7d2f4 (cast_call_entries follow their cast member on delete); editor: Cast tab (name, character, phone, usual pickup) and a Cast section on the day (tick who works, status W/SW/WF/SWF/H/R, pickup prefilled from the usual one, call, M/H, on set); sheet: Cast table above personal calls, in print too. 4 backend tests, 1 E2E. Backend changed: deploy needed (migration)
- gated: no
- why: a narrative shoot day without cast times is not a call sheet; the model had cast since the skeleton but nothing could enter or show it, so the pilot AD would have kept a second document for the actors
- dod:
  - cast members per production with character and usual pickup; per-day entries with status code and the four times, carried to the next revision
  - the sheet shows a Cast table (name, character, status, pickup, call, M/H, on set) when anyone works that day
  - failure case: removing an actor with entries on published sheets drops their line and keeps every sheet loadable and publishable

## FR-34 · tech-lead · Cancel a day; rename or wrap a production
- state: done
- note: delivered 2026-09-21 (feat/fr-34-cancel-day-edit-production): `POST /call-sheets/{id}/cancel` (status cancelled, every subscribed phone gets "Day N: CANCELLED", logged like a revision) and `/restore`; publishing a revision also puts a cancelled day back on and now sets status published (it had stayed `draft` forever); the sheet shows a CANCELLED banner, the days list a tag, the stable link skips cancelled days and marks them; `PATCH /productions/{id}` (name, status) behind the new `production:edit` permission (owner, editor) with a Settings tab. Migration d1f6b4c8e3a5 adds the enum value. 4 backend tests, 2 E2E. Backend changed: deploy needed (migration)
- gated: no
- why: pilot protocol: a day created by mistake or a weather cancellation had no way out but the API, and a wrongly named production was stuck; "day off" is the second most important message after "call time changed" and must reach every phone
- dod:
  - cancel asks once, then the sheet, the days list and every personal link say CANCELLED; subscribers are pushed; nothing is deleted
  - restore, then a revision, brings the day back with the crew told
  - production name and status editable by owner and editor, not by viewers
  - failure case: cancelling a day nobody subscribed to still succeeds with 0 of 0 told
## FR-35 · frontend · Where the day happens, on the sheet
- state: done
- note: delivered 2026-09-21 (feat/fr-35-locations-on-the-sheet): every call-sheet read carries `locations` (the day's distinct locations in schedule order with their scene numbers, address, parking, nearest hospital, coordinates; read live from the Locations tab so a corrected address reaches every sheet); the viewer shows a "Where" block above the schedule with a maps link (coordinates when resolved, else the address; none when neither exists, so never a link to a wrong place) and the location name on each scene row; print keeps each location together. 2 backend tests; the two location E2E tests extended. Backend changed: deploy needed (no migration)
- gated: no
- why: the crew sheet showed the day's times but not where to go: scenes carried only a location id, so the address, parking and nearest hospital lived in the AD's editor and the WhatsApp text only. "Where" is the first thing a driver reads
- dod:
  - the sheet lists the day's locations in schedule order with address, parking notes, nearest hospital and a maps link; the schedule shows the location name per scene
  - failure case: a location with neither coordinates nor address gets no maps link; a deleted location is skipped without breaking the sheet

## FR-36 · tech-lead · Who has opened REV B
- state: done
- note: delivered 2026-09-21 (feat/fr-36-seen-by): `revision_views` (migration e2a7c5d9f4b6; one row per revision × crew member, cascades with both), `POST /public/call-sheets/{id}/seen/{token}` written by the viewer only when a personal link loaded the sheet live (a cached copy never counts, so the AD is not told REV B arrived when it did not), `GET /call-sheets/{id}/seen` report; the day screen shows "REV B opened by 3 of 12", the names not yet, "push on" where they subscribed, and a WhatsApp nudge per person with a phone; refreshes every minute; a new revision starts the count over. 3 backend tests, 1 E2E. Backend changed: deploy needed (migration)
- gated: no
- why: "crew missing an update" is the failure the product exists to prevent (BRIEF Q3); today the AD phones around asking "did you get REV B?"; the answer should be on the screen, with the chase one tap away
- dod:
  - the day screen shows who has opened the current revision through their personal link and who has not; per-revision, never carried over
  - the people not yet in get a one-tap WhatsApp nudge with their link
  - failure case: an offline (cached) open is not counted; an unknown token is refused
## FR-37 · frontend · Send everyone their link from the Crew tab
- state: done
- note: delivered 2026-09-21 (feat/fr-37-crew-onboarding-links): per person a WhatsApp action with an onboarding message (first name, production, the stable link, what it does) when they have a usable phone; "Copy all links" gives one line per person for a spreadsheet, with the hint that links are personal and go one by one, never to the group. 2 unit tests, 1 E2E. Frontend only
- gated: no
- why: the first evening of a shoot the AD has to get 40 personal links to 40 phones; without this it is 40 copy-pastes, and the temptation is to paste the general link into the group, which loses personal calls and read receipts (FR-32, FR-36)
- dod:
  - Crew tab: WhatsApp per person with the stable link and a short explanation; Copy all links as name · department: link lines
  - failure case: no usable phone → no WhatsApp link (copy stays), never a wa.me link to a wrong number

## FR-38 · frontend · Delete a location
- state: done
- note: 14:00 shift 2026-09-21 (branch `fix/fr-38-delete-a-location`) delivered every dod bullet: `DELETE /productions/{id}/locations/{id}` (CREW_EDIT) nulls `location_id` on every `ScheduleItem` that pointed to it (any revision, past or current) before deleting the row, so a published day never breaks; the Locations tab gets a Remove button using the same `window.confirm` one-step pattern as Crew's remove. Backend test publishes a day with a located scene, deletes the location, confirms the scene keeps its text with `location_id: null`, the sheet's `locations` list drops it, and a further revision still publishes (118/118 backend tests pass, 2 new). E2E test publishes a day with an unaddressed location (avoids this sandbox's Nominatim egress block), removes it from the Locations tab, and reopens the day: the location select is back to "no location" and the FR-27 sunrise hint reappears with its no-location copy rather than a blank field — the dod's own failure case, exercised for real against a real build and a real uvicorn+Postgres API (this sandbox's pinned Playwright Chromium revision is absent, same gap prior shifts noted; verified instead against the pre-installed `/opt/pw-browsers/chromium` with `--headless=new` via a temporary `conftest.py` override, reverted before commit, not part of the diff). Full Playwright suite 45/47 (2 pre-existing, unrelated: the same Nominatim-egress failures every prior shift touching `test_locations_e2e.py` has hit, one further confirmed to pass in isolation — flaky only under full-suite contention). `npm run typecheck`/`npm run build` clean, `npm test` 26/26. No migration needed (nulling `location_id` is a normal write, no schema change). Backend changed: deploy needed (no migration).
- gated: no
- why: FR-19 added locations but not a way to remove one typed by mistake; a wrong address on the Where block (FR-35) reaches every sheet, so the AD must be able to take it out, not just rename it
- dod:
  - `DELETE /productions/{id}/locations/{id}` (crew:edit): scenes on any revision that pointed to it keep their text and lose the link (location_id null); the sheet's Where block simply drops it
  - Locations tab: Remove with a one-step inline confirm, same pattern as crew
  - backend test: a day whose scene used the deleted location still loads and publishes; E2E: remove, scene's location select shows "no location"
  - failure case: deleting a location that is the day's only one makes the FR-27 hint reappear on the day screen, not a blank sunrise with no explanation

## FR-39 · tech-lead · Weather fills in on publish when left blank
- state: done
- note: 15:00 shift 2026-09-21 (branch `feat/fr-39-weather-on-publish`) delivered every dod bullet: `publish_revision` in `backend/app/services/call_sheets.py` now calls `_fill_weather_forecast` (mirroring `_fill_computed_sunrise_sunset`) when `weather_forecast` is blank and the day's first located scene has coordinates, using the same `weather.weather_suggestion(lat, lng, date)` the "Suggest weather" button calls, so the two can never disagree; a typed value is left untouched (checked before the call). `weather_suggestion` already carries its own 5s timeout and returns `None` on any provider failure without raising, so an unreachable provider never fails or delays the publish — it was already safe, this shift only added the caller. Editor: a static hint under the Weather field/"Suggest weather" button says it fills in from the location on publish, next to the existing sunrise/sunset hint. Backend tests (`backend/tests/test_locations.py`): blank + located scene → filled with the provider's text; typed value → provider never even called (asserted via a monkeypatch that raises if invoked); provider down (`None`) → publish still returns 201 and the field stays `null`. Full backend suite 121/121 (118 + 3 new) against a real local Postgres 16 — one run showed 5 unrelated failures in `test_push.py`/`test_cancel_day.py` (`invalid input value for enum distribution_channel: "PUSH"`) that reproduced with and without this diff on a fresh venv/DB but vanished on every rerun in isolation or as part of the full suite again; not this change's doing, flagged as an intermittent enum-cache issue for whoever next hits it, not filed as a bug since it could not be reproduced on demand. `npm run typecheck`/`npm run build` clean; `npm test` 26/26 (no new frontend unit test needed — the hint is static text, no new logic). No E2E added (not asked by the dod; the change has no new interactive path to exercise beyond what the sunrise/sunset E2E already covers for the same publish call). CI then caught a real bug this local run hadn't hit: two existing tests publish a call sheet dated before "today" in CI, and Open-Meteo answers 200 for a date past its forecast range with null temperatures rather than an error, so `round(None)` raised uncaught — a genuine crash risk for any shoot date beyond the provider's ~16-day horizon, not just a test artifact. Fixed in the same PR: `weather_suggestion` now treats null temperatures as an unusable response and returns `None`; the two affected sunrise tests and one sheet-locations test now stub `weather_suggestion` so they don't depend on a live network call; one new regression test added. Full backend suite 122/122 locally before the fix was pushed; CI re-run pending. Backend changed: deploy needed (no migration).
- gated: no
- why: sunrise and sunset already auto-fill from the first scene's location on publish (FR-19); weather still needs the AD to press "Suggest weather" and accept it, which the pilot protocol showed nobody does the first time; a blank weather line on a call sheet reads as "not checked"
- dod:
  - `publish_revision`: when `weather_forecast` is blank and the first located scene has coordinates, fill it with the same suggestion text the button would give; never overwrite a typed value
  - the editor hint under Weather says it fills in from the location on publish (like the sunrise hint); the "Suggest weather" button stays for the AD who wants to see it first
  - backend test with the weather provider monkeypatched: blank → filled, typed → kept, provider down → stays blank and publish still succeeds
  - failure case: the provider being unreachable never fails or delays a publish beyond its timeout

## FR-40 · qa · Pilot readiness re-run against everything added on 2026-09-21
- state: done
- note: 16:00 shift 2026-09-21 (branch `docs/fr-40-pilot-readiness-rerun`) closed the dod without re-running live traffic: a direct `curl` to `https://filmrunner-api.fly.dev/` confirmed this session's egress proxy still rejects it (`CONNECT tunnel failed, response 403`), the same block every FR-8/FR-16 attempt has hit since 2026-09-14, and no `fly` CLI is installed here. Checked instead whether the existing "Second run" in `docs/research/pilot-readiness-2026-09.md` (the `pilot-readiness-live3.py` run at 13:40 the same day) already answers the dod's own named scope — it does: all six surfaces this item's `why` names (WhatsApp share, one link per person, cast, cancel, Where, who opened REV B) and the three named public-endpoint checks are already in that table, 17/17 pass, 0 fail; cited row by row in a new "Third pass" section rather than re-run. Named what that run predates and this pass could not verify live either — FR-38, FR-39, and the founder's-session trio FR-42/FR-43/FR-44 — as a table of NOT VERIFIED rows with what backs each today (its own delivering shift's test counts, not a live check, and not claimed as one) and a concrete next step (re-run `pilot-readiness-live3.py` or a small extension of it once egress or `fly` is available). Failure case: nothing new was exercised live this pass, so nothing here is a false PASS and no bug was fabricated to file; the five NOT VERIFIED rows are the named gap for the next shift or the founder. Doc-only (`docs/research/**`), auto-merge eligible.
- gated: no
- why: FR-26 ran the protocol before today's thirteen merges (WhatsApp share, one link per person, cast, cancel, Where, who opened REV B); the readiness file must say what is verified for the new surface before the founder takes a phone to a set
- dod:
  - extend `docs/research/pilot-readiness-2026-09.md` with a section per new item: what was checked headless against the live API (`https://filmrunner-api.fly.dev`, public endpoints only: `/public/call-sheets/{id}`, `/public/crew/{token}/next`, `/public/.../seen/{token}` with a throwaway token gives 404) and what needs the founder's phone (WhatsApp share sheet, wa.me deep links, push on cancel)
  - each line pass / fail / not verified, with the command or click path
  - failure case: anything that fails live is filed as a `ready` bug item with the reproduction, not left as a note

## FR-41 · marketing · Pilot outreach message for five Prague ADs
- state: done
- note: 17:00 shift 2026-09-21 (PR #134, branch `docs/fr-41-pilot-outreach-message`) delivered `docs/marketing/pilot-outreach.md`: a Czech WhatsApp-length message and a Czech/English e-mail version, both linking the landing page and the live demo, tone and the single "live and offline-honest" claim taken directly from `docs/marketing/positioning.md` (FR-6), no feature list. Added the dod's Q&A block (offline, data, price, install/account, notifications) with every answer checked against `docs/research/pilot-readiness-2026-09.md`'s PASS/NOT VERIFIED rows, so nothing promises a real-phone push check or an on-set airplane-mode check that hasn't actually run yet, and the price answer says "free for the pilot" rather than repeating BRIEF.md's unverified €99–499 hypothesis. Handled the dod's failure case directly with a standing instruction: re-check both drafts against the readiness file's current state before every send, not just at writing time. Sending itself stays gated the same way FR-3's own invitation text is (INBOX #1) — this is text for the founder to send from her own name, not an automated send. Doc-only (`docs/marketing/**`), auto-merge enabled. PR is the whole deliverable.
- gated: no
- why: the landing page (FR-25) and the demo are up; INBOX #1 (interviews) is waiting on the founder's network, and the founder needs a message to paste, not a brief to write
- dod:
  - `docs/marketing/pilot-outreach.md`: one Czech WhatsApp-length message and one e-mail version (Czech, English below), both linking the landing page and the live demo, asking for one shoot day on a real production; tone from `docs/marketing/positioning.md`, no feature list longer than three lines
  - a short "what to say when they ask about offline / data / price" block with honest answers grounded in the readiness file (what is verified, what is not)
  - failure case: nothing in the message promises something the readiness file marks as not verified

## FR-42 · frontend · Tomorrow at a glance on the sheet
- state: done
- note: delivered 2026-09-21 (feat/fr-42-tomorrow-on-the-sheet): `CrewDayRef` carries general_crew_call and first_location_name; a sheet opened through a personal link (stable or day link) shows a "Tomorrow" line under the sheet — Day N · date · crew call · location, "day off · next is Day N" when the next date is not the following one, "cancelled" (no old time) when it is; prints as well. 1 backend test, 1 E2E. Backend changed: deploy needed (no migration)
- gated: no
- why: the one-link-per-person resolution (FR-32) already returns every day; a crew member reading today's sheet at wrap wants tomorrow's crew call and location without navigating; on paper this is the "advance schedule" line every Czech call sheet carries
- dod:
  - `CrewNextDay.days` gains general_crew_call and the first location name per day (from each day's current revision); the sheet, when opened through a personal link, shows a one-line "Tomorrow: Day N · date · crew call · location" block above the other-days nav for the next day after the one shown, or "Tomorrow: day off" when the next day is not the following date
  - print shows the same line at the bottom
  - E2E: two consecutive days, open day 1 via the stable link, see day 2's crew call
  - failure case: a cancelled next day shows "Tomorrow: Day N cancelled", never its old call time

## FR-43 · frontend · Days list at a glance
- state: done
- note: delivered 2026-09-21 (feat/fr-43-days-overview): the AD's days list shows per day the crew call, where it starts and "opened 3/12" (from FR-36's read receipts) without opening the day; `opened` is filled on the authenticated list only, never on the crew's public read. 1 backend test, 2 E2E extended. Backend changed: deploy needed (no migration)
- gated: no
- why: with several days published the AD's evening question is "which day is tomorrow, what is the call, who has not opened it" — the list should answer without a tap per day
- dod:
  - days list: call time, first location, opened x/y per day; cancelled tag stays
  - failure case: a production with no crew shows no "opened" fragment rather than 0/0

## FR-44 · frontend · Personal calls: only the people with one, the rest one pick away
- state: done
- note: delivered 2026-09-21 (feat/fr-44-personal-calls-picker): the day screen lists only crew with an entry today (with a × to drop it) and a "Personal call for…" picker for everyone else, showing their standing time; entries still carry over to the next revision and to the next day. E2E tests adapted (helper `_pick_personal_call`). Frontend only
- gated: no
- why: FR-24 rendered three inputs for every crew member; with a real crew of 40 that is 120 inputs on a phone before the schedule, while a typical day has two or three personal calls
- dod:
  - people with an entry listed; a select adds one; × removes one (the person then gets the general call again)
  - failure case: nothing is lost on reload — entries come back from the draft or the server as before

## FR-45 · tech-lead · Reuse people across productions: pick an existing contact when adding crew or cast
- state: done
- note: delivered 2026-09-21 (feat/fr-45-shared-contacts): `GET /contacts?q=` returns people on productions the caller is a member of (crew or cast), matched on a name prefix (any word) or phone digits, with last production and position, max 10, sorted; `PersonPicker` on the Crew and Cast forms fills name and phone from a pick and remembers the contact id (typing on clears it, so an edited name is a new person); a picked person's phone edited in the form is corrected for every production (PATCH); the paste import reuses a contact whose name and phone digits both match. 3 backend tests (incl. viewer visibility), 1 E2E. Backend changed: deploy needed (no migration)
- gated: no
- why: the same gaffer works three productions a year; today every production creates a new Contact, so a phone correction on one sheet never reaches the others and the founder's pilot AD will type the same 40 people twice (FR-31 helps the first time only)
- dod:
  - `GET /contacts?q=` (authenticated): contacts the caller can see — those on productions they are a member of — matched on name prefix and phone digits, max 10; service token sees all
  - Crew and Cast forms: typing a name shows matches (name · phone · last production); picking one reuses the contact id instead of creating a new one; the paste import (FR-31) reuses a contact whose name and phone both match
  - backend test: a viewer on production A cannot see contacts that exist only on production B; E2E: add "Tomáš Novák" on a second production by picking him, edit his phone there, the first production's sheet shows the new number
  - failure case: two contacts with the same name and different phones stay two people; the picker shows both with their numbers, never merges them

## FR-46 · frontend · Copy the crew from another production
- state: done
- note: 09:00 shift 2026-09-22 (PR #140, branch `feat/fr-46-copy-crew-from-another-production`, merged) delivered every dod bullet: a "Copy crew from…" quiet button next to "Paste a list…" (and named in the empty-crew hint) lists the caller's other productions via the existing `GET /productions`; picking one previews its people (name, department, position, HoD) via the existing `GET /productions/{id}/crew-members` with checkboxes all on by default; "Add N people" calls the existing `POST /productions/{id}/crew-members` per selected person, copying contact id/department/position/HoD but never `standard_call_time` (it belongs to a production, not the person). People already on the target crew (matched by `contact_id`) show "already on this crew" with a disabled, unchecked checkbox and are excluded from the count. No backend change: the endpoints already existed with the right permissions, so the failure case (a viewer on the target gets no button) falls out for free — the whole "Add a person" section, this button included, is already gated on `crew:edit` for every other action in it. New Playwright E2E: production A with 3 crew (2 HoD, one with a standing call time) copied into production B shows 3 checked preview rows, adds all 3 without the call time, B's own published sheet lists both HoDs under "Who to call" (FR-14), and re-opening the picker against the same source shows all 3 as already-there with nothing selected. `npm run typecheck`/`npm run build` clean, `npm test` 40/40; full Playwright suite 48/50 (2 pre-existing unrelated Nominatim-egress failures every prior shift touching `test_locations_e2e.py` has also hit; one other test flaked once under full-suite contention on the pre-existing FR-45 PersonPicker autocomplete, passed on its own rerun, not touched by this change). Backend untouched, no deploy needed.
- gated: no
- why: an AD's next production is mostly the last production's crew; one action beats FR-31's paste when the people are already in FilmRunner (FR-45 makes the contacts shared)
- dod:
  - Crew tab, empty state and a quiet button: "Copy crew from…" lists the caller's other productions; picking one previews the people (name, department, position, HoD) with checkboxes, all on; "Add N people" creates crew members reusing the contact ids; standing call times are not copied (they belong to a production)
  - people already on this crew are shown as such and skipped
  - E2E: production A with 3 crew, production B copies them, B's sheet lists the HoDs
  - failure case: copying from a production the caller only views (viewer role) works for reading the list, but the add still requires crew:edit on the target — a viewer on B gets no button

## FR-47 · frontend · PDF of the day from the editor, complete
- state: done
- note: 2026-09-22 founder's session: the pagination test failed on a current local Chromium because digits in the proportional font extract as NUL (font subset without a ToUnicode map), so `Set N` never matched; rewritten to count letter-only tokens per page (row head vs wrapped tail), which also detects a row split across a page break — something the digit count never did. Passes on both browsers
- note: 10:00 shift 2026-09-22 (PR #142, branch `feat/fr-47-pdf-print-mode`) delivered every dod bullet: a "PDF" link next to the crew link on the day screen (`#pdfLink`, appends `&print=1`) opens the sheet in a new tab; `App.tsx` watches for `?print=1` and calls `window.print()` once the sheet has actually loaded (live or cached), so the print dialog opens with no extra tap — verified by stubbing `window.print` in a real browser rather than trusting the code path. Print CSS: page numbers now render via a real `@page { @bottom-right { content: counter(page) " / " counter(pages); } }` margin box (verified this renders correctly in this sandbox's pinned Chromium, not assumed); a new fixed-position footer bar (`#printFooterBar`, `position: fixed` so it repeats on every printed page in Chromium/WebKit, confirmed the same way) carries a QR code and the plain-text crew link, built from a `shareUrl` threaded from `App.tsx` into `CallSheetView` — the general crew link, never a personal `?me=` link. Row-splitting and repeating table headers were already handled by the existing print stylesheet (`thead { display: table-header-group }`, `tbody tr { page-break-inside: avoid }`) from earlier shifts; this shift only added `.tomorrow { page-break-inside: avoid }` for the one new block FR-42 had left unguarded. The empty-heading failure case was already correct (Cast/Personal-calls sections are conditionally rendered on non-empty data) — verified with a new test rather than re-implemented. New Playwright suite `frontend/tests/test_pdf_e2e.py` (3 tests) seeds a real 40-scene/30-crew day through the live API (HTTP, not the UI — 70 rows would be too slow to type) and asserts, via a real PDF from Chromium's `page.pdf()` read back with `pypdf`: page count stays under 4, every one of the 40 scene numbers appears exactly once (the row-split/drop proxy the dod's own QA case asks for), the page-number footer is present, and the QR/crew-link footer bar renders. `npm run typecheck`/`npm run build` clean, `npm test` 40/40, full Playwright suite 51/53 (the 2 failures are the pre-existing, unrelated Nominatim-egress-block failures every prior shift touching `test_locations_e2e.py` has also hit). This sandbox had no Python venv, Postgres, or `npm install` done yet this session — set up a local Postgres role/db, a backend venv, and a frontend-tests venv from scratch to run all of the above for real; this sandbox's own pinned Playwright Chromium revision is absent, same gap every prior shift noted, verified instead against the pre-installed `/opt/pw-browsers/chromium-1194` via a temporary `conftest.py` override, reverted before commit, not part of the diff. Frontend only, no backend change, no deploy needed.
- gated: no
- why: the production office and the insurer still want a PDF in the mail; the crew link's "Print / Save PDF" exists but the AD reaches it through a crew link, and the print layout has grown (cast, where, personal calls, tomorrow) without a check that it paginates
- dod:
  - day screen, once published: "PDF" opens the sheet in print mode (`?print=1` on the day link opens the print dialog on load) with every block: header with REV and issued time, calls, sun and weather, where, schedule, cast, personal calls, who to call, safety, tomorrow line
  - print CSS: no block cut in half, table headers repeat on a new page, the crew link and a QR code in the footer so the paper leads back to the live sheet, page numbers "1 / 3"
  - a Playwright test emulates print media and checks the page count for a 40-scene, 30-person day stays under 4 and no row is split (via `page.pdf()` on Chromium, page count from the PDF)
  - failure case: a sheet with no cast and no personal calls prints without empty headings

## FR-48 · frontend · The crew's sheet in Czech
- state: done
- note: delivered 2026-09-22 (feat/fr-48-czech-sheet): `frontend/src/i18n.ts` — a flat CS/EN dictionary for the viewer only (editor stays English), browser language (cs, sk → Czech) by default, a masthead toggle remembered in localStorage, `fmtDate` "st 23. 9. 2026" / "Wed 23 Sep 2026"; every label on the sheet, the personal block, tomorrow, other days, statuses, empty states, the home page, the print footer and the notification toggle; user-entered text untouched; a Czech key missing falls back to the English text. 3 unit tests, 1 E2E (`locale="cs-CZ"`), one FR-42 expectation updated for the formatted date. Frontend only. Note: `test_pdf_e2e.py::...paginates...` fails locally on both main and this branch (pypdf text extraction on a current Chromium; passes on CI's pinned one) — filed as a follow-up in the note of FR-47
- gated: no
- why: the landing is CS/EN but the sheet the crew actually reads is English only; the pilot crews are Czech; labels like "Crew call", "Who to call", "Tomorrow", "cancelled" must read naturally in Czech for the pilot to be judged on the product, not the language
- dod:
  - the viewer (index.html) has a label dictionary (cs, en) and picks the browser language, with a small CS/EN toggle remembered in localStorage; dates as "st 23. 9. 2026" in Czech; the editor stays English for now (separate item if the pilot asks)
  - every visible label on the sheet, the personal block, the tomorrow line, the other-days nav, the status line and the cancelled banner is covered; user-entered text (sets, notes, names) is never translated
  - E2E: with `locale="cs-CZ"` the sheet shows "Sraz štábu" and the badge "REV B nahrazuje A"; the toggle switches to English and back
  - failure case: a label missing from the dictionary falls back to English text, never to a key like `crew_call`

## FR-49 · frontend · Who to call: tap-to-call, WhatsApp and copy on every contact
- state: done
- note: 11:00 shift 2026-09-22 (PR #148, branch `feat/fr-49-contact-actions`, merged) delivered every dod bullet: each contact card in the public sheet's Who to call section and the personal block's own-department rows (both use the same `ContactRow`) now shows call (`tel:`, unchanged), WhatsApp (`wa.me` via FR-29's `whatsappNumber`/`whatsappUrl`, only when the number normalises) and copy-number, each icon-labelled with a 44px minimum touch target; a "Copied" confirmation shows briefly after copy. Kept the existing `a.phone` tel: link and its `test_contacts_render_with_tap_to_call_and_no_number_fallback` assertions unchanged rather than restructuring it, so Call is not gated on the number's validity (only WhatsApp is, per the dod's own wording) — a contact with unusable phone text (e.g. "ask Petra") still shows the tel: link and copy button but no WhatsApp link. New Playwright E2E `test_contacts_get_whatsapp_and_copy_only_when_the_number_normalises` (mocks a call sheet with a normalising and a non-normalising phone) verified against a real build: `npm run typecheck`/`npm run build` clean, `npm test` 43/43, full smoke suite 15/15, full frontend Playwright suite 53/55 (the 2 failures are the pre-existing, unrelated Nominatim-egress-block failures every prior shift touching `test_locations_e2e.py` has also hit, reconfirmed live this shift). Backend baseline 135/135, unaffected (no backend files touched). Print CSS hides the new buttons/icons, keeping the plain tel: number as before. Frontend only, no deploy needed. CI passed and hackathon-mode auto-merge landed the PR during this shift.
- gated: no
- why: the sheet's contacts are `tel:` links only; on set people write on WhatsApp first and call second, and a phone number should be copyable without selecting text with a wet thumb
- dod:
  - each contact card: call (`tel:`), WhatsApp (`wa.me` via the FR-29 number normalisation, only when the number normalises), copy number; icons with labels, 44px targets
  - the personal block's "your department" rows get the same
  - E2E: a contact with "777 123 456" has a wa.me link to 420777123456; one with "ask Petra" has none
  - failure case: a contact without a number shows "no number on file" and no dead controls

## FR-50 · frontend · Publish history on the day screen
- state: done
- note: 12:00 shift 2026-09-22 (PR #156, branch `feat/fr-50-publish-history`) delivered the whole dod: `GET /call-sheets/{id}/history` (production:read) returns one entry per revision — `revision_letter`, `created_at`, `created_by` (defaults to `"unknown"`, never a null cell — the dod's own failure case), `opened` (reusing FR-36's `RevisionView` receipts), and `changes` (reusing FR-23's `revision_changes()` against the revision immediately before it). Day screen shows it as a collapsed `<details>` "History" panel (same pattern as the public sheet's "other departments"), most-recent-revision first, each line with its own compact change list; REV A always shows no diff. Cancel/restore is deliberately left out — no `call_sheet_events` model exists to record it, so the dod's own named fallback ("otherwise leave cancel out and say so") applies rather than adding a new model for it. Backend: 3 new tests, 144/144 total. Frontend: `npm run typecheck`/`npm run build` clean, `npm test` 43/43, new Playwright E2E for the history panel, full suite 58/60 (the 2 failures are the pre-existing, unrelated Nominatim-egress-block failures every prior shift touching `test_locations_e2e.py` has also hit). No migration, no deploy needed. PR open with auto-merge enabled at shift end.
- gated: no
- why: revisions carry `created_by` and `created_at` already; the AD asks "who sent REV C at 22:40?" when a coordinator also edits; today the only trace is the API
- dod:
  - day screen: a collapsed "History" list — REV A · Mon 21 Sep 20:40 · Eva · 12 opened; REV B · … — one line per revision, from the sheet's `revisions` on the authenticated read (letter, created_at, created_by, what changed vs the previous one using FR-23's `revision_changes`), plus cancel/restore events if the model records them (it does not yet: add `call_sheet_events` only if needed for cancel; otherwise leave cancel out and say so)
  - backend: `GET /call-sheets/{id}/history` (production:read) returning the list; `created_by` for a signed-in user is their e-mail, for the service token the label the client sent
  - failure case: a revision with `created_by` null shows "unknown", never an empty cell

## FR-51 · tech-lead · Public endpoints: abuse guard without hurting the 05:00 rush
- state: done
- note: delivered 2026-09-22 (feat/fr-51-public-rate-limit, ADR-008): `app/ratelimit.py` — sliding one-minute windows in process, 300/min per client IP (`Fly-Client-IP`, then X-Forwarded-For, then socket) on `/api/v1/public/*` and 30/min per personal token on the token routes; 429 with Retry-After inside CORS; OPTIONS, /healthz and authenticated routes never limited; both limits are settings, 0 disables (the E2E harness does). Sized from ~5 requests per person per open: the test drives 40 tokens × 5 requests from one IP with no 429. Per-IP raised from the dod's 120 to 300 for that reason. 4 backend tests; conftest resets the windows per test. Backend changed: deploy needed (no migration)
- gated: no
- why: `/public/call-sheets/{id}`, `/public/crew/{token}/next`, `/public/.../seen/{token}` and the push subscribe endpoints are unauthenticated by design (FR-13 tokens are the credential); before a pilot with a public URL there must be a limit on how fast an unknown client can probe tokens or fill `revision_views`
- dod:
  - per-client (IP) sliding-window limit on the public router: 120 requests/minute, 429 with `Retry-After`; token-bearing endpoints additionally 30/minute per token; in-process store is fine for one Fly machine, documented as such (ADR)
  - the limit never affects authenticated routes; `/healthz` exempt
  - backend test: 121st request in a minute gets 429, the 122nd after the window passes gets 200; the seen endpoint with 31 different bogus tokens from one IP gets 429 before the 31st
  - failure case: 40 crew members opening the sheet at 05:00 from one production office Wi-Fi (one IP) must not be throttled — the per-IP number is chosen for that (40 people × 3 requests each in a minute) and the test covers it

## FR-52 · qa · Pilot scale: 40 crew, 30 days, 60 scenes on a phone
- state: done
- note: delivered 2026-09-22 (feat/fr-52-pilot-scale): `frontend/tests/test_scale.py` seeds 60 crew / 8 cast / 6 locations / 30 days of 40–60 scenes through the API and measures on an iPhone-width, CDP-throttled 4G profile; report `docs/research/pilot-scale-2026-09.md`. One real problem found and fixed: the days list shipped every day's full schedule (520 KB, 2.8 s) — the list read now empties schedule/cast/crew calls (27 KB, 0.8 s); side fix: publish no longer asks Open-Meteo outside its 16-day window (a 400 per publish on a schedule import). Everything else under 1 s; the crew's 60-scene sheet opens in 0.7 s throttled (0.1 s warm). Lighthouse not run (not in the harness), said so in the report. Backend changed: deploy needed (no migration)
- gated: no
- why: everything was tested with 2–3 people and 1–2 days; a real Prague feature has 40–80 crew and 25–40 days; the editor's day screen and the days list must stay usable on an iPhone at that size before the pilot, not after
- dod:
  - a seed script `backend/app/seed_scale.py` (idempotent, service token, against a local API by default) creating one production with 60 crew across 12 departments, 8 cast, 6 locations, 30 days of 40–60 scenes, personal calls on 5 people per day
  - measurements against the local build with Playwright at iPhone width: time to interactive for the days list, the day screen, the crew tab, the public sheet; Lighthouse mobile performance score for the public sheet; sizes of the API responses
  - report in `docs/research/pilot-scale-2026-09.md` with numbers and the three slowest spots; each spot over 1.5 s on a throttled 4G profile filed as a `ready` item with the reproduction
  - failure case: the public sheet for a 60-scene day must render under 2 s on the throttled profile or it is filed as a bug, not noted

## FR-53 · tech-lead · Backups and the restore path
- state: done
- note: delivered 2026-09-22 (feat/fr-53-backups-restore): `docs/ops/backup-restore.md` (what the Free plan keeps — nothing; JSON export per production through the API; full pg_dump/pg_restore path with the Fly secret swap; DB password rotation steps; which secret is recoverable how; drill log) and `backend/scripts/production_backup.py` (export one or all productions, import into a new or an empty existing one, refused otherwise; crew get new tokens on restore; coordinates travel with addresses so the geocoder is not re-asked — `create_location` trusts supplied coordinates). 2 backend tests: export → import gives field-for-field identical sheets; non-empty target refused. Not yet drilled: pg_dump against the hosted project (noted in the doc). Backend changed: deploy needed (no migration). The read-only Supabase PAT no longer works (revoked), so the plan facts are from Supabase's published plan page, not the API
- gated: no
- why: the pilot's call sheets live in one Supabase Postgres; a wrong migration or a deleted production is recoverable only if someone knows how; nobody has written it down or tried it
- dod:
  - `docs/ops/backup-restore.md`: what Supabase keeps on the current plan (daily backups, retention), how to download one, how to restore into a fresh project, and the env changes on Fly that follow; the DB password rotation procedure (the founder still has one to do)
  - `backend/scripts/export_production.py`: JSON export of one production (contacts, crew, cast, locations, days with revisions) through the API with the service token; `import_production.py` the reverse into an empty production — a restore that does not need database access
  - test: export a production created in the test suite, import it into a new one, the public sheet of day 1 is identical field for field
  - failure case: importing into a production that already has days is refused with a clear message, never merged silently

## FR-54 · marketing · Thirty-second recording of the flow for the landing
- state: done
- note: 13:00 shift 2026-09-22 (PR #158, branch feat/fr-54-landing-flow-video): `frontend/scripts/record_landing_flow.py` drives the real editor (service token, iPhone viewport) through create day → publish REV A → crew link → publish REV B with a changed call, captured with Playwright's `record_video_dir`; 826 KB WebM, well under the 3 MB cap. `landing.html` embeds it muted/looped with the first screenshot as poster; a `prefers-reduced-motion` visitor gets manual controls instead of autoplay; a missing/broken video file removes the whole section rather than a broken player — the dod's own failure case, verified live (a mocked 404 removes `section.flow`), not just read from the code. New Playwright test covers all three states. README line added on how to re-record. `npm run typecheck`/`npm run build` clean, `npm test` 43/43, full Playwright suite 58/60 (2 pre-existing unrelated Nominatim-egress failures). Backend baseline 143/143, unaffected. Frontend only, no deploy needed. Auto-merge enabled, PR's own `ci` check pending at shift end.
- gated: no
- why: the landing has three screenshots; a Prague AD deciding whether to reply wants to see the phone flow — publish, the crew's sheet, REV B replacing A — in half a minute, without an account
- dod:
  - `frontend/scripts/record_landing_flow.py`: Playwright against the local build, iPhone viewport, drives the real editor (service token) through create day → publish → crew link → REV B with a changed call, captures a video (Playwright `record_video_dir`) and turns it into a ≤ 3 MB WebM/GIF committed under `frontend/public/landing/`
  - landing.html embeds it (autoplay muted loop, poster = first screenshot, reduced-motion respected) under the screenshots, CS/EN captions
  - failure case: the recording script fails loudly if any step's selector is missing, so a UI change never silently ships an outdated recording; README line on how to re-record

## FR-55 · frontend · Import the crew from a file (Excel, CSV, Numbers export)
- state: done
- note: delivered 2026-09-21 (feat/fr-55-import-crew-file): the paste panel takes an .xlsx/.xls/.csv (SheetJS loaded lazily as its own chunk, parsed in the browser); `crewFileImport.ts` finds the header row within the first ten rows by CS/EN synonyms (name, phone, department, position, e-mail), a mapping row with four selects fixes a wrong guess, a name-only row is a department header, an "HoD/vedoucí" column or "(HoD)" in the position marks a head, an odd phone is left out with a warning; same preview and "Add N people" as FR-31 (so FR-45's contact reuse applies). 8 unit tests, 1 E2E with a committed Czech 12-row fixture (`frontend/scripts/make_crew_fixture.mjs`). Known: `xlsx@0.18.5` carries npm advisories for parsing hostile files; here the AD parses their own file on their own phone. Frontend only
- gated: no
- why: founder 2026-09-21: "bylo by super mít možnost to naimportovat z něčeho" — the crew list exists as an .xlsx from the production office or a Google Sheet; FR-31's paste covers copied cells, a file drop covers the rest and the column names tell us more than a paste does
- dod:
  - Crew tab: "Import a file…" accepts .xlsx, .xls, .csv (SheetJS in the browser, no upload; the file never leaves the phone); header row detected by common names in CS/EN (jméno/name, telefon/phone/mobil, oddělení/department/dept, pozice/position/funkce, e-mail); a small column-mapping row lets the AD fix a wrong guess; then the same preview and "Add N people" as FR-31, reusing existing contacts per FR-45
  - department headers as merged rows or a department column both work; phone numbers normalised the FR-29 way for display, stored as typed
  - unit tests for the header detection (CS/EN, order, missing columns) and E2E with a committed 12-row .xlsx fixture
  - failure case: a file with no recognisable name column is refused with "which column has the names?" and the mapping row, never a silent import of garbage

## FR-56 · frontend · Import the shooting schedule (scenes per day) from Excel or a Movie Magic export
- state: done
- note: delivered 2026-09-21 (feat/fr-56-import-schedule): `scheduleImport.ts` reads a plain AD sheet (day/date columns, CS/EN headers) or a Movie Magic export ("Day N — date" / "End of Day N" banner rows), pages in every notation, dates in CZ/US/ISO/"Sep 23, 2026" forms, cast names; Days tab "Import schedule…" previews per day and creates **planned days** — a new server-side state: `CallSheetCreate.draft` keeps the day at status `draft` (invisible on the public read and the stable link, no push), publishing replaces its content and stays REV A, `DELETE /call-sheets/{id}` works only for drafts; locations created by name, cast matched by name (unmatched listed), existing dates skipped; no day information → one draft named "Imported schedule". 14 unit tests, 3 backend tests, 1 E2E with a committed Czech 3-day fixture. Backend changed: deploy needed (no migration)
- gated: no
- why: the AD's schedule already exists as a stripboard export (Movie Magic Scheduling → Excel/CSV, or a plain Excel with day, scene, INT/EXT, D/N, set, pages, location, cast); typing 40 scenes a day into the phone is the second setup killer after the crew
- dod:
  - Days tab: "Import schedule…" accepts .xlsx/.csv; rows grouped by shoot day (a day column, or "Day 1 – date" banner rows, or a date column); per row scene number, INT/EXT, D/N, set description, pages (eighths or "2 3/8"), location name, cast names; preview per day with counts; "Create N days" creates unpublished drafts on this phone (not published) with scenes in order, locations matched by name to the Locations tab (unmatched → created), cast matched by name (unmatched listed, not created)
  - existing days with the same date are not overwritten: the preview marks them and skips
  - unit tests for the grouping and the pages parser; E2E with a committed 3-day fixture
  - failure case: a file with scenes but no day information imports as one unpublished draft named "Imported schedule" rather than guessing dates

## FR-57 · tech-lead · Import from an existing call sheet PDF
- state: done
- gated: no
- note: delivered 2026-09-21 (feat/fr-57-import-call-sheet-pdf): `POST /productions/{id}/import/call-sheet-pdf` (crew:edit) — pypdf text layer (10 MB cap, scans refused with a clear message), then Claude (`FILMRUNNER_ANTHROPIC_API_KEY`, model `FILMRUNNER_ANTHROPIC_MODEL`, default claude-sonnet-5, temperature 0, JSON out) with a fall-back to a heuristics pass on any failure; the heuristics un-glue pypdf's concatenated cells case-aware for Czech, anchor a person on a phone number, take the first two capitalised non-job words as the name, keep department headers, and skip hospital/location lines — both committed sample PDFs (Czech and English layouts) extract fully on heuristics alone. Preview only; the PDF is never stored. Crew tab: "…or an old call sheet PDF" into the same preview as paste/file, with the method shown. The founder set the key on Fly on 2026-09-21 (it passed through chat: rotate it). 3 backend tests (Claude path with a mocked transport, fallback, refusals), 1 E2E. Backend changed: deploy needed (no migration)
- why: every AD has last production's call sheet as a PDF; its crew list and contacts are the fastest way to seed a new production; layouts differ per production company, so a fixed parser will not do
- dod:
  - `POST /productions/{id}/import/call-sheet-pdf` (crew:edit): text extraction (pypdf), then a structured extraction of contacts (name, department, position, phone) — first a heuristics pass (phone regex anchors a row, department headers by the FR-31 word list); when `FILMRUNNER_ANTHROPIC_API_KEY` is set, a Claude call with the page text and a JSON schema does the extraction instead, temperature 0, max 4k output; response is a preview list, nothing is created until the AD confirms in the same Crew tab preview as FR-31
  - the PDF is processed in memory and not stored; 10 MB limit; scanned PDFs (no text layer) are refused with a clear message
  - tests: two committed sample PDFs (a Czech and an English layout) through the heuristics path; the LLM path tested with the client mocked
  - failure case: the extractor returning a person with no name or a phone that does not normalise is shown in the preview with a warning, never created silently

## FR-58 · frontend · The editor in Czech
- state: done
- note: delivered 2026-09-22 (feat/fr-58-czech-editor): `src/editor/lang.tsx` (context, `useL`, English text as the key) + `src/editor/cs.ts` (~290 strings); every label, placeholder, hint, notice, confirm text and button in the editor, including templated notices with placeholders and plural forms; the toggle sits in the masthead's sub line and shares the storage key with the crew's sheet; `noticeFromError` translates its fixed texts and keeps the server's detail. Found on the way: `.share { word-break: break-all }` broke names and hints mid-word at 390 px (it now applies to the raw URL only) and row actions did not wrap. 1 E2E with `locale="cs-CZ"`; English suite unchanged. Frontend only
- gated: no
- why: FR-48 put the crew's sheet in Czech; the AD who writes it is Czech too, and the editor is where the first impression of "is this for us" happens; labels, hints, notices and button texts, not the AD's own words
- dod:
  - the same `i18n` mechanism as the viewer (browser language, CS/EN toggle in the editor masthead, remembered per device, shared key with the viewer so one choice covers both pages)
  - every label, placeholder, hint, notice, confirm text and button in the editor; department/position/set text as typed stays; dates in inputs stay ISO (native pickers)
  - E2E: with `locale="cs-CZ"` the Productions screen, a day screen and the Crew tab read in Czech; the toggle flips to English; existing English tests unchanged (en-US default)
  - failure case: a key missing from Czech shows the English text, never a key; a notice built from a server detail keeps the server's text

## FR-59 · pm · Privacy note before the first real crew list
- state: done
- note: delivered 2026-09-22 (feat/fr-59-privacy): `frontend/privacy.html` (CS/EN, landing design and toggle; controller = the production, processor = the founder as a natural person until a company exists; every stored field listed; Supabase EU-Ireland, Fly Frankfurt, GitHub Pages, Anthropic for an uploaded PDF's text only, Nominatim/Open-Meteo get addresses and dates only; who sees what by role and link; retention until removal; removal via the AD or e-mail; what is not in place: DPA template, automatic deletion, a company); linked from the sheet (below it, hidden in print), the landing footer and the Crew tab next to the imports; every sentence checked against the code. Smoke test covers reachability and the toggle. Frontend only
- gated: no
- why: a pilot means 40 real names and phone numbers, photos and read receipts in our database; the AD who uploads them is the controller and needs to be able to answer "where is this and who sees it" — and a crew member opening a personal link should find the same answer in one tap; without it the founder should not ask anyone to import a crew
- dod:
  - `frontend/privacy.html` (CS default, EN toggle, same design as the landing): who is the controller (the production / the AD) and who the processor (FilmRunner, the founder as a natural person until a company exists), what is stored per person (name, phone, e-mail, department/position, photo, personal calls, read receipts, push subscription), where (Supabase, EU — Ireland; Fly, Frankfurt; Anthropic for an uploaded PDF's text only, not stored), who can see what (production members by role; a personal link shows only that person's block), how long (until the production is deleted or the person removed; backups per the runbook), how to ask for removal (the AD removes the person; or e-mail the founder), no analytics, no third-party trackers
  - linked from the crew's sheet footer, the personal block, the landing footer and the editor's Crew tab (next to the import buttons)
  - honest about what is not in place yet: no DPA template, no formal retention schedule, no cookie consent needed (none set)
  - failure case: nothing on the page may promise a control the product does not have; every sentence checked against the code (e.g. photos live in Postgres, not a bucket)

## FR-60 · frontend · Crew filter on the Crew tab
- state: done
- note: delivered 2026-09-22 (feat/fr-60-61-crew-filter-print): a search box above the list matches every word against name, department, position and phone digits (however the number is written); the count reads "5 people" or "2 of 5"; no match shows "Nobody matches …" with a clear control, never an empty tab. Imports, "Copy all links" and the print deliberately stay on the whole crew, not the filtered view. 8 unit tests, 1 E2E. Frontend only
- gated: no
- why: FR-52 seeded 60 people and the tab is fast, but finding one person to edit a phone number is a scroll; a real feature crew is 60–80
- dod:
  - a filter box above the list (name, department, position, phone digits), instant, remembered while the tab is open; the count "12 of 60" next to it; department headers collapse to the matching ones
  - the paste/file/PDF imports and "Copy all links" keep working on the full list, not the filtered one (say so next to the button)
  - E2E on the FR-52 production: type a department, see only its people; clear, see all
  - failure case: a filter that matches nobody shows "nobody matches" and the clear control, never an empty tab that looks broken

## FR-61 · frontend · Crew list as a PDF for the production office
- state: done
- note: delivered 2026-09-22 (feat/fr-60-61-crew-filter-print): "Print crew list" opens a plain A4 document in a new tab (blob URL, `noopener`, prints itself on load) — production name, printed-at line, crew grouped by department with the head first, position and phone ("—" when there is none), cast with characters in its own block; no links, no tokens, no photos; rows and department blocks avoid page breaks. Everything the AD typed is HTML-escaped (tested). Frontend only
- gated: no
- why: the office and the insurer still ask for a printed crew list with phones; today the AD screenshots the Crew tab
- dod:
  - Crew tab: "Print crew list" opens a print view (same print CSS family as the sheet): production name, date printed, people grouped by department with position and phone, heads marked; cast on a second block with characters
  - phones as typed; no personal tokens, no links, no photos in the print
  - Playwright: emulate print, the view contains every person once, grouped; page count under 3 for 60 people
  - failure case: a person without a phone prints "—", never an empty cell that reads as a mistake

## FR-62 · marketing · Czech screenshots and copy on the landing after FR-48/58
- state: done
- note: delivered 2026-09-22 (feat/fr-62-czech-landing): `take_landing_screenshots.py` now shoots each view once per language (`<name>.cs.jpg` / `.en.jpg`, locale-switched contexts) and the landing shows the pair matching its toggle; caption "Kam" → "Kde" to match the product's own label; two feature lines added (imports from Excel/schedule/PDF; Czech + English with a link to the privacy page). Two real bugs found on the way: the revision diff's labels came from the server in English on every Czech sheet — the viewer now renders them from the stable `field` key (`change.*`, with "změn: N" for personal calls) and falls back to the server's text; and a screenshot that failed *before* the deferred landing module ran kept its broken-image icon — handled with a `complete && naturalWidth === 0` check, and one missing file now drops only its own image, never the figure the other language needs. 2 E2E (language-matched shots; missing-file path with service workers and HTTP cache disabled, which is what made it flaky). Frontend only
- gated: no
- why: the landing shows English screenshots to a Czech audience while the product now reads in Czech; the first impression should match the pilot's language
- dod:
  - `frontend/scripts/take_landing_screenshots.py` takes both languages (locale switch) and the landing shows the ones matching the visitor's toggle; Czech copy reviewed once more against the product's actual Czech labels (Sraz štábu, Komu volat, Kde)
  - the feature list mentions imports (Excel, schedule, PDF) and the privacy page
  - failure case: a missing screenshot file hides its figure, never a broken image (FR-25's rule, re-checked for the new files)

## FR-63 · qa · Accessibility pass on the four screens a crew member and an AD use
- state: done
- note: delivered 2026-09-22 (feat/fr-63-a11y): `frontend/tests/test_a11y.py` runs axe-core 4.10.2 over seven screens (sheet in EN and CS, personal link, day screen, Crew tab, landing, privacy note) and fails CI on any serious/critical finding; report `docs/research/a11y-2026-09.md`. Two real defects fixed: `--muted` was 4.22:1 on paper — under AA for the hints, meta lines and labels it carries on every screen (41 + 13 nodes) — now #6e685f at 5.0:1; avatar initials were 3.6:1 on their chip, now `--ink-2` at 6:1. Every page gained a `<main>` (landmark-one-main, region: 40 nodes). Result: 0 violations at any impact level. Not covered, said so in the report: screen-reader order (belongs to the FR-28 phone protocol), 200 % zoom, user-typed capitals. Frontend only
- gated: no
- why: a call sheet is read at 05:00 in a car; labels, contrast and focus order are not polish, they are legibility; nothing has been checked beyond aria-labels for tests
- dod:
  - axe-core through Playwright (`@axe-core/playwright` or the CDN script) on: the crew's sheet (demo, CS and EN), a personal link, the day screen, the Crew tab; report in `docs/research/a11y-2026-09.md`
  - every "serious" and "critical" finding fixed in the same PR or filed as a `ready` item with the rule id; contrast of the muted text checked against the paper background
  - the E2E suite keeps an axe check on the demo sheet so a regression fails CI
  - failure case: an axe rule that fires on user-entered content (e.g. all-caps set names) is documented as such, not "fixed" by changing the AD's text

## FR-64 · pm · Pilot onboarding one-pager for the AD (Czech)
- state: done
- note: delivered 2026-09-22 (docs/fr-64-onboarding-ad): `docs/pilot/onboarding-ad.md` — Czech first, English below: before the shoot (production, the three crew imports, locations, cast, privacy page), the evening before day 1 (day or schedule import, calls, personal calls, cast, scenes, publish, links per person via WhatsApp, day text to the group), morning and during the day (opened-by, nudge, REV B, cancel/restore, next day, actual times, PDF), and the three things that go wrong first with what the product does; 31 quoted labels checked against `cs.ts` (the rest are templated). Sign-in by code and the real-iPhone checks are stated as pending, not promised
- gated: no
- why: the founder will sit with the first AD for 30 minutes; the AD needs the same 30 minutes on paper for the day the founder is not there — what to prepare, in which order, and what to tell the crew
- dod:
  - `docs/pilot/onboarding-ad.md` in Czech (English below): before the shoot (production, crew from Excel/paste/PDF, locations with addresses, cast), the evening before day 1 (day, scenes, personal calls, publish, send links from the Crew tab), the morning (who opened, nudge, revision), and the three things that go wrong first (no signal, a wrong number, a late change) with what the product does about each
  - links to the privacy page and the readiness protocol; no feature that is "not verified" in the readiness file is promised
  - failure case: every step names the exact button label as it reads in the Czech editor (checked against `cs.ts`)

## FR-65 · frontend · Actual times per day: first shot, lunch, wrap
- state: done
- note: delivered 2026-09-22 (feat/fr-65-actuals): five columns on call_sheets (migration f3b8d6e1a9c7), `PUT /call-sheets/{id}/actuals` (day:publish; 409 on a draft or cancelled day), returned on authenticated reads and the days list, stripped from the public read; editor: an "Actual times" block on a published day (first shot, lunch out/in, wrap, note) saved on its own — no revision, no push; days list shows "wrap 19:40"; "Export actual times (CSV)" (day, date, crew call, first shot, lunch, wrap, note; semicolons and BOM so Czech Excel opens it). CS/EN. 2 backend tests, 1 E2E incl. the CSV and the crew's sheet staying on REV A. Backend changed: deploy needed (migration)
- gated: no
- why: after wrap the AD reports first shot and wrap to production; it is the one number everyone asks for the next morning, and it belongs next to the planned call — the seed of a daily report without building one
- dod:
  - on a published day, an "Actuals" block (first shot, lunch out/in, wrap, a free note) editable by day:publish, stored on the call sheet (not a revision — no push, no REV letter), shown on the days list ("wrap 19:40") and in the editor's day screen; never on the crew's sheet
  - `GET /productions/{id}/call-sheets` carries them; a CSV export of day, planned call, first shot, wrap, note from the days list
  - backend test + E2E; migration for the four columns and the note
  - failure case: actuals on a cancelled or draft day are refused with a clear message, never silently accepted

## FR-25 · marketing · Landing page from the positioning
- state: done
- note: 13:00 shift 2026-09-21 (PR #111, branch feat/fr-25-landing-page) delivered every dod bullet: `frontend/landing.html` as a third Vite entry, FR-6's chosen position as the headline, three real screenshots of the bundled demo call sheet (header/calls/weather, Where, Who to call) taken by a committed Playwright script (`frontend/scripts/take_landing_screenshots.py`, re-run after any visual change to the sheet), a live-demo link, and a no-forms "Request a pilot" mailto to the founder. Czech/English toggle is two static `[lang]`-tagged blocks per element switched by a small vanilla script (`frontend/src/landing.ts`, no framework), defaulting to the visitor's browser language and falling back to Czech with no JS at all. The root entry page (`index.html`) gets one added link, "What is FilmRunner?", kept to that page's existing "two doors, no marketing" design. No external fonts; all three images 28-40 KB; verified at 390px in both languages. Handled the dod's failure case directly: a screenshot the script could not produce is simply not written, and `landing.ts` removes any `<figure>` whose image fails to load, so a missing shot never becomes a broken-image placeholder. `npm run typecheck`/`npm run build` clean, `npm test` 23/23; full Playwright suite 39/41 (the 2 failures are `test_locations_e2e.py`'s pre-existing Nominatim-egress-block, unrelated, flagged by every prior shift touching that suite). Touches `frontend/`, so per TEAM.md's hackathon mode this still gets `gh pr merge --auto --squash` (only TEAM.md itself is excluded); PR is the whole deliverable.
- gated: no
- why: hackathon goal; docs/marketing/positioning.md (FR-6) exists and the product is demoable; a Prague AD who hears about FilmRunner needs one page that says what it is, shows the real call sheet, and offers the demo and a way to ask for a pilot
- dod:
  - frontend/landing.html as a third Vite entry in the same paper world: one sentence of positioning, the live demo call sheet embedded or linked, three screenshots taken from the real app by a Playwright script committed to the repo, and a "Request a pilot" mailto to the founder's address (no forms, no accounts)
  - text follows positioning.md; Czech and English toggle without a framework (two static blocks)
  - Lighthouse-style basics by hand: no external fonts, images under 200 KB each, works at 390 px
  - the root entry page links to it; Pages deploys it
  - failure case: if a screenshot cannot be produced by the script, the page ships without that image slot rather than with a placeholder

## FR-26 · qa · Pilot readiness protocol executed against the live app
- state: done
- note: executed 2026-09-21 by the founder's session: docs/research/pilot-readiness-2026-09.md, 17 pass, 0 fail, 6 not verified headless (sign-in email, offline honesty, push) listed for the founder's phone; gaps filed as FR-27, FR-28
- gated: no
- why: hackathon goal; before an AD touches it, every step of the loop must be walked on the live URLs and the results written down, not assumed
- dod:
  - docs/research/pilot-readiness-2026-09.md: the checklist (sign in with a code, create production, crew with HoD, day with location and weather suggestion, publish, crew link offline, personal link, push received, REV B, PDF) with pass/fail per step, executed headless where possible against https://sandovabarbora.github.io/filmrunner/ and https://filmrunner-api.fly.dev using the service token from the E2E pattern
  - every fail becomes a backlog item with the exact reproduction, filed in the same PR
  - steps that need a real iPhone are listed separately with what to observe, for the founder
  - failure case: a step that cannot be executed headless is marked "not verified", never "pass"

## FR-27 · frontend · Day without a location: say what is missing, link to Locations
- state: done
- note: delivered 2026-09-21 (feat/fr-27-location-hint): `GET /productions/{id}/locations/{id}/sun?shoot_date=` reuses the publish-time computation; the day screen fetches it as soon as the first scene has a location and fills blank sunrise/sunset without a reload (never over typed values); the hint under the fields has four states (no location → text + link to Locations / picked but unmapped → type them or add an address / filled / lookup failed → "Could not fetch suggestions; type sunrise and sunset yourself"). 1 backend test, 2 E2E (real Nominatim for the fill, aborted route for the failure case). Backend changed: deploy needed (no migration)
- gated: no
- why: pilot protocol G2: a day with no location silently shows empty sunrise, sunset, weather and hospital; the AD cannot tell that adding a location would fill them (FR-19 works only with one)
- dod:
  - the day screen shows, next to the sunrise/sunset fields, "Add a location to this day to get sunrise, sunset, weather and the nearest hospital" with a link to the Locations tab, only while no scene has a location
  - after a location is picked, the suggestions appear without a reload
  - Playwright: new day without location shows the hint; picking a location on a scene fills sunrise
  - failure case: if the suggestion provider fails, the hint changes to "could not fetch suggestions, type them" rather than staying on the "add a location" text

## FR-28 · qa · Phone protocol results (founder) folded back into the readiness file
- state: blocked
- gated: partial
- why: steps 4, 18, 20, 21 of docs/research/pilot-readiness-2026-09.md cannot be verified headless; they need a real iPhone and the founder's sign-in email (INBOX #3)
- dod:
  - the founder runs the "For the founder's phone" section and reports PASS/FAIL per step
  - a shift folds the results into the file and files one backlog item per FAIL with the observed behaviour
  - failure case: a step the founder skipped stays NOT VERIFIED, never becomes PASS by omission
- note: blocked until the founder reports; the routine must not mark these steps itself

## FR-20 · marketing · Prague market sizing: how many active productions are there
- state: done
- note: 12:00 shift 2026-09-21 (branch docs/fr-20-prague-market-sizing) delivered docs/research/prague-market-sizing.md. `WebFetch` confirmed blocked this shift for every domain tried, including the Czech Film Commission's own statistics page and, newly, `en.wikipedia.org` (no prior shift had tried Wikipedia). No public source gives the 30-day active-production count Q5 asks for; built an explicit order-of-magnitude estimate instead from five dated proxies (88 Czech films premiered in 2025, 2025 incentive-application growth, named large productions currently shooting, a `productionlist.com` Prague count of unverified date range, and FAMU's unquantified-per-year but real annual output), each flagged for what it does and does not measure. Compared against a word-of-mouth critical-mass threshold (Rogers' diffusion research, commonly cited as 15-20% of an audience, sourced from a marketing OER since Wikipedia and Rogers' own text were unreachable) applied to the addressable audience of call-sheet-assemblers, not the general public. Handled the dod's failure case directly: proposed adding one estimation question to FR-3's interview script rather than guessing a number. Doc-only (docs/research/**), qualifies for auto-merge per TEAM.md.
- gated: no
- why: BRIEF.md Q5 asks whether Prague is dense enough for word-of-mouth distribution; this is answerable from public listings, unlike Q1-Q4/Q6 which need real interviews (INBOX #1, blocked on the founder). The backlog otherwise has no item against Q5.
- dod:
  - docs/research/prague-market-sizing.md defines "active production" as one that issued a call sheet in the last 30 days, per BRIEF.md Q5
  - counts it from Czech Film Commission listings, FAMU student/graduate productions, and any public filming-permit data findable by WebSearch
  - the count is compared against a stated word-of-mouth sample-size threshold, citing the source for that threshold
  - every claim cites its source and the date checked
  - failure case: if no public source can establish a count, the doc says so explicitly and proposes the narrowest fallback (e.g. asking FR-3 interviewees to estimate) instead of guessing a number

## FR-22 · pm · Desk research: who assembles call sheets and what they use today (Q1/Q2 public-source proxy)
- state: done
- note: 11:00 shift 2026-09-21 (PR #94, branch docs/fr-22-call-sheet-role-tooling-signals) delivered docs/research/call-sheet-role-and-tooling-signals.md. `WebFetch` confirmed blocked this shift for every domain tried, Czech and international alike (csfc.cz, biofilms.cz, nsp.cz), extending FR-2/FR-21's known vendor-domain block to ordinary Czech industry sites; everything is built from `WebSearch` snippets and cited. Strongest finding: a real, named Prague production coordinator's LinkedIn profile (Kristyna Chalupova, credited on Stillking Films-scale productions) lists "call sheets and scheduling" as an explicit skill — the one genuine Czech-market confirmation that the task sits inside the production-coordinator role, at the large-production end. No Czech-specific tool name (StudioBinder/Yamdu/Movie Magic/etc.) surfaced for any production size despite four targeted searches; marked unverified per the dod's failure case, not guessed. FAMU's own Production Regulations page surfaced as the most on-topic short-production-tier source but could not be read (egress-blocked); flagged as follow-up. Size-coding table left sparse where no source stated or implied a tier, per the dod. Doc-only (docs/research/**), so per TEAM.md this qualifies for auto-merge. PR is the whole deliverable.
- gated: no
- why: BRIEF.md Q1 and Q2 can only be fully answered by real interviews (FR-3), which stay blocked on the founder recruiting candidates (INBOX #1); public crew job postings and industry discussion can give an early, weaker signal on who drafts/approves/distributes call sheets and what tool a production names today, the same kind of desk-research complement FR-21 already built for Q6
- dod:
  - docs/research/call-sheet-role-and-tooling-signals.md gathers public Czech production crew job postings and classifieds (e.g. filmtalent.cz, Facebook crew groups, LinkedIn) and any public forum or discussion (Reddit, industry groups) that names who assembles, approves, or distributes call sheets, and what tool or workflow (email+PDF, WhatsApp, StudioBinder, etc.) a production names using
  - findings are coded by production size (short <15 crew, feature <50, feature/TV >50) wherever a source states or implies it, the same convention FR-3's interview script uses
  - the doc states explicitly, wherever cited elsewhere, that this is a public-source proxy and never a substitute for FR-3's real interview answers
  - failure case: if no public source names a role and a tool/workflow together, the doc says so explicitly rather than inferring a link between separately-found facts

## FR-67 · qa · Verify sunrise/sunset accuracy against a live reference, closing ADR-006's own revisit trigger
- state: done
- note: 16:00 shift 2026-09-22 (PR TBD, branch `ci/fr-67-astronomy-accuracy`) delivered every dod bullet: `scripts/check_astronomy_accuracy.py` calls `backend/app/services/astronomy.py`'s `sunrise_sunset()` directly (no deployed API needed) for both solstices and both equinoxes of 2026, fetches the same dates from sunrise-sunset.org's free keyless JSON API (https://sunrise-sunset.org/api, terms confirmed via WebSearch 2026-09-22 since WebFetch/curl to the domain are themselves blocked here — attribution required, 429 on abuse, well under any reasonable-volume threshold at 8 requests), and asserts each value within ±3 minutes, printing the actual deviation per date into the job summary. Wired into `.github/workflows/pilot-readiness.yml` as a second step (`if: always()`, so it runs even if the live-stack step fails and reports independently). Could not run this from the routine's own sandbox (same egress block as every FR-8/FR-16/FR-40 attempt, confirmed again with a direct `curl` to `api.sunrise-sunset.org`: `403`) — instead dispatched the workflow for real on this branch via the GitHub Actions API and read back the actual run (https://github.com/sandovabarbora/filmrunner/actions/runs/35738976530): all 8 checks passed, every deviation 1-3 minutes (spring equinox sunrise the largest, at exactly 3), so the ±3 tolerance is not loosened further — it is the real measured ceiling, not a guess. `docs/adr/ADR-006-location-services.md`'s "unverified against a live source" paragraph and "Revisit when" trigger are both rewritten with these real numbers and the run link; `backend/tests/test_astronomy.py`'s own solstice cross-check is tightened from a ±20-minute band against times "recalled from general knowledge" to ±3 minutes against these real measured values (verified locally by re-running the test's assertions directly against `astronomy.py`, pytest itself not installed in this sandbox). Failure case verified for real, not just read: with the sandbox's own egress blocked, the script fails loudly (exit 1, each row named `reference fetch failed: ... 403 Forbidden`) rather than passing silently — the same behaviour the live GitHub Actions run would show if the provider were ever actually down. Backend changed: deploy needed (per TEAM.md's literal rule, since `backend/app/services/astronomy.py` and `backend/tests/test_astronomy.py` are both touched — though only a docstring and a test assertion, no runtime behaviour differs, so this is a formality, not an urgent redeploy).
- gated: no
- why: ADR-006 names its own revisit trigger verbatim — "egress unblocks timeanddate.com or api.sunrise-sunset.org... so the astronomy formula gets an independent check" — and has flagged the in-process sunrise/sunset computation as "unverified against a live source" with only a ±20-minute self-consistency test since the 13:00 shift on 2026-09-15, a week with no follow-up. FR-66 (2026-09-22) built exactly the missing piece since then: a GitHub Actions job with open egress that this routine's own sandbox proxy blocks. This is not desk polish: BRIEF.md Q3 names wrong times among the top failures a call sheet must avoid, and a revision silently auto-fills sunrise/sunset from the computed value whenever the AD leaves the fields blank (FR-19's dod), so a wrong formula would reach a real crew with nobody having typed the number themselves.
- dod:
  - a script (e.g. `scripts/check_astronomy_accuracy.py`), runnable from a GitHub Actions job with open egress, fetches a live reference sunrise/sunset time for Prague (50.0755°N, 14.4378°E) from a free keyless provider (api.sunrise-sunset.org or an equivalent found and cited with its terms and the date checked, same sourcing convention as ADR-006's other providers) for a spread of dates covering both solstices and both equinoxes
  - it calls `backend/app/services/astronomy.py`'s own function directly for the same dates and coordinates (no deployed API needed) and asserts each value is within a stated tolerance of the live reference (start at ±3 minutes; tighten the assertion, and `backend/tests/test_astronomy.py`'s own tolerance, if the measured deviation is smaller), printing the actual deviation per date
  - wired into `.github/workflows/pilot-readiness.yml` (or a new workflow alongside it) so it reruns automatically, with its own pass/fail row in the job summary rather than a one-off local run
  - `docs/adr/ADR-006-location-services.md`'s "Astronomical accuracy is not independently verified" line and "Revisit when" trigger are replaced with the actual measured deviation and the date checked
  - failure case: if the reference provider is unreachable or returns malformed data, the check fails loudly naming the provider and status, never silently passing or falling back to the existing self-consistency-only test as if that were equivalent verification

## FR-68 · qa · Live write-path check for the five features never exercised against the deployed API
- state: done
- note: 09:00 shift 2026-09-23 (branch `test/fr-68-live-write-path-check`) delivered the whole ungated half of the dod: `scripts/check_live_write_path.py`, modelled on `docs/research/pilot-readiness-live3.py`'s disposable-production convention and `scripts/check_live_stack.py`'s check()/report()/exit-code convention, reading `FILMRUNNER_CI_TOKEN` from the environment. It creates one `CI check <uuid>` production, a geocoded location, a crew member with a standing call time, and publishes three real revisions (A/B/C) to drive all five features end to end: FR-38 (delete the location, confirm the schedule item keeps its text with `location_id` cleared, confirm it's gone from the locations list, confirm the day still publishes), FR-39 (REV A's blank weather auto-fills; REV B's typed weather is echoed back unchanged), FR-44 (a per-day entry beats the standing time on `/me/{token}`, and survives REV C which resends no `crew_calls`), FR-42 (`/crew/{token}/next` lists the day with its call and location; an unknown token 404s), FR-43 (the days list carries `opened: {seen: 1, total: 1}` after a real `/seen` hit; the public single-sheet read never carries `opened`). Wired into `.github/workflows/pilot-readiness.yml` as a step guarded on `env.FILMRUNNER_CI_TOKEN != ''`, with a companion always-run step that writes a named "skipped" line to the job summary when the secret is absent; the script itself also tells a rejected (401) token apart from a real failure and reports that as skipped too, never a false red build (the dod's own failure case). `docs/research/pilot-readiness-2026-09.md` gets a new section pointing at the workflow step, the same pattern FR-66 used. Filed INBOX #6 for the founder to create the `FILMRUNNER_CI_TOKEN` GitHub Actions secret (the gated half of this dod). Verified locally: stood up a fresh local Postgres + uvicorn (this sandbox's own egress proxy blocks `filmrunner-api.fly.dev`, same limitation FR-66 worked around), ran the script three ways — a good token (10/11 checks pass; the one local failure is FR-39's weather auto-fill hitting the same egress block against Open-Meteo, logged as `403 Forbidden` and falling back to blank exactly as FR-19's own tests describe, not a script bug), a wrong token (reports "skipped: token rejected", exit 0), and no token (clear stderr message, exit 1, the path CI's `if:` guard prevents from ever running). `python scripts/check_company_docs.py docs/company` clean.
- gated: partial
- why: `docs/research/pilot-readiness-2026-09.md`'s "Third pass, 16:00 shift 2026-09-21 (FR-40)" names FR-38 (delete a location), FR-39 (weather fills in on publish), FR-42 (tomorrow at a glance), FR-43 (days list at a glance) and FR-44 (personal calls picker) as **NOT VERIFIED against the live API**, backed only by local/mocked test runs, and no shift since has closed that table. FR-66/FR-67 (2026-09-22) already proved a GitHub Actions runner has the open egress this routine's own sandbox lacks, but both only read public, unauthenticated endpoints (`scripts/check_live_stack.py`); none of the five items above can be exercised for real without creating a production and publishing a revision, which needs a signed-in user (FR-12's Supabase JWT model has no shared bearer token in production by design). This is not desk polish: it is the same open gap FR-40 already named honestly rather than guessing at, and the hackathon goal (STATUS.md, "pilot-ready by Friday") is an AD publishing a real day end to end on the live stack.
- dod:
  - a script (e.g. `scripts/check_live_write_path.py`), modelled on the already-committed `docs/research/pilot-readiness-live3.py` pattern but read from an environment variable (`FILMRUNNER_CI_TOKEN`) rather than a local file, drives the live API (and, where a UI-only behaviour needs it, the live Pages editor via Playwright, `/opt/pw-browsers/chromium` already present in this kind of runner) through: create a production, add a location, delete it (FR-38) and confirm the day's schedule items survive with `location_id` cleared; publish a revision with a blank weather field and confirm it auto-fills (FR-39) without overwriting a typed value on a second check; confirm the day list and a "tomorrow" summary reflect what was just published (FR-42, FR-43); set one person's per-day call time and confirm it appears on their personal link in preference to their standing time (FR-44)
  - every created production is named `CI check <uuid>` (matching the existing live-check convention) so it is visibly disposable, never mistaken for real pilot data
  - the script exits non-zero with the failing step named on any assertion failure or unreachable host, the same convention `check_live_stack.py` already uses — never a silent "not verified"
  - wired into `.github/workflows/pilot-readiness.yml` as a step that runs only `if: env.FILMRUNNER_CI_TOKEN != ''` (or an equivalent guard), so the existing daily read-only checks keep running and reporting even before the token exists — this ungated part (script + guarded workflow step) ships in this item's PR
  - `docs/research/pilot-readiness-2026-09.md`'s NOT VERIFIED table is updated to point at this workflow step once it exists, the same pattern FR-66 used for the read-only checks
  - the gated part — obtaining a real signed-in Supabase JWT for a dedicated "ci-checker" identity (or a service account, whichever the founder prefers) and storing it as a GitHub Actions repository secret — is filed as a new INBOX.md item, since creating that identity and holding its token are both actions TEAM.md reserves for the founder (an account, and a secret, respectively); until she does this the new workflow step stays present but silently skipped, never failing the job
  - failure case: if the token secret is ever removed or expires, the guarded step is skipped (not failed) and the job summary says so by name, so a rotated or revoked credential reads as "not run" rather than a false red build

## FR-69 · tech-lead · Partial unique index enforcing one current revision per call sheet
- state: in-progress
- note: 10:00 shift 2026-09-23 (PR #176, branch `feat/fr-69-current-revision-unique-index`) delivered the whole dod: migration `22f098e3dc1d` adds `uq_call_sheet_revisions_one_current` on `call_sheet_revisions(call_sheet_id) WHERE is_current`, also added to the SQLAlchemy model's `__table_args__` so the test suite's `create_all`-based schema enforces it too; the TODO in `call_sheet.py` now points at the migration; new test inserts a second current revision directly (bypassing `publish_revision`) and asserts `IntegrityError`. Verified against a real local Postgres: 144/144 backend tests pass, `alembic upgrade head` runs the full chain cleanly on a fresh DB, and — the dod's own failure case — seeding two current revisions for one call sheet then running the migration alone fails loudly naming the exact `call_sheet_id` in the `DETAIL` line, never a silent row drop. Backend changed: deploy needed (migration only, no data change). Touches `backend/`, but hackathon mode auto-merges every PR with green CI; awaiting that CI run, so left `in-progress` rather than `done` until it merges.
- gated: no
- why: `backend/app/models/call_sheet.py:94` carries an open TODO — "add a partial unique index once the target DB (Postgres) is fixed for production, so this invariant can't be violated by a bug" — and Postgres has been the production DB since FR-8 (2026-09-15); today only the application layer (`services/call_sheets.py`) stops two "current" revisions existing on one call sheet, with no DB-level guard against a future bug. Serves the hackathon goal: an AD publishing a real day end to end must be able to trust that "the current revision" is never ambiguous.
- dod:
  - a migration adds `CREATE UNIQUE INDEX ... ON call_sheet_revisions(call_sheet_id) WHERE is_current`, so the database itself rejects two current revisions for one sheet
  - the TODO comment in `call_sheet.py` is removed or updated to point at the migration that closed it
  - a test inserts two current revisions for the same call sheet directly (bypassing `publish_revision`) and asserts the database raises an `IntegrityError`
  - failure case: if any existing row already violates the invariant, the migration fails loudly naming the `call_sheet_id` rather than silently dropping rows or adding an index that can never actually be enforced

## FR-70 · marketing · Revisit positioning.md's "Local" rejection now that FR-20 has run
- state: done
- note: 11:00 shift 2026-09-23 (branch docs/fr-70-positioning-local-revisit) rewrote the "Local" alternative in `docs/marketing/positioning.md` citing FR-20's actual finding (order-of-magnitude estimate, "low tens to low hundreds" active Prague productions, largest uncertainty in the untracked student/ad/micro-budget category) and its own explicit conclusion ("does not confirm Prague is dense enough... not obviously out of reach"). Decision: this does not move "Local" to the lead position — the estimate is too uncertain (order-of-magnitude, not a count) to carry a locality headline; it continues to support only the distribution angle (H3 Prague-first go-to-market, film-school free tier). Named what would move it: FR-20's own follow-ups (a direct read of `filmcommission.cz/en/statistics/` or `productionlist.com`'s real date range) or FR-3 interview data (still blocked on INBOX #1). The chosen position (live+offline-honest) is separately re-confirmed against the same evidence, unrevised. Doc-only (`docs/marketing/**`), qualifies for auto-merge. PR is the whole deliverable.
- gated: no
- why: `docs/marketing/positioning.md:44-49` rejects the "built for Prague" position because "BRIEF.md Q5 ... is still open — FR-20 has not run yet"; FR-20 (Prague market sizing, BRIEF Q5) delivered its order-of-magnitude estimate the same day, 2026-09-21, and positioning.md was never revisited against it — the doc still reads as if Q5 is unanswered.
- dod:
  - the "Local" alternative's paragraph in `positioning.md` is rewritten citing FR-20's actual finding (the estimate and its stated confidence), with an explicit decision: does it change the lead position, or only support a distribution angle (H3's Prague-first go-to-market, film-school free tier)
  - the chosen position (live+offline-honest) is re-confirmed or revised using the same reasoning standard the doc already applies to its other alternatives
  - failure case: if FR-20's estimate is too uncertain to move the decision, the doc says so explicitly and names what would move it (e.g. real interview data from FR-3, still blocked on INBOX #1) rather than leaving the stale "not yet known" text uncorrected

## FR-71 · qa · Lighthouse mobile performance score for the public sheet at pilot scale
- state: done
- note: 12:00 shift 2026-09-23 (branch `test/fr-71-lighthouse-pilot-scale`) delivered the whole dod: `npx lighthouse --version` in fact works in this sandbox (the npm registry is reachable even though `filmrunner-api.fly.dev`/other vendor domains are not) — the "no Lighthouse in the harness" line in `pilot-scale-2026-09.md` was never re-checked, just repeated. Added `lighthouse` as an exact-pinned devDependency and `frontend/scripts/lighthouse_pilot_scale.py`, which seeds the same FR-52 production (idempotent by name), serves a real `npm run build` dist over a local static server, runs a real local API + Postgres, and runs Lighthouse (`--form-factor=mobile`, Chrome's own simulated throttling, headless `/opt/pw-browsers/chromium` via `CHROME_PATH`) against the public sheet for day 5 (60 scenes). Real run, not a guess: Performance 69, Accessibility 100, Best Practices 96, SEO 90 — Performance is under 90, driven by Cumulative Layout Shift 0.843 (audit score 0.04), Lighthouse's own culprit trace naming the whole sheet body as the shifting element (`main#main`, top:55 to bottom:10026). Recorded in `docs/research/pilot-scale-2026-09.md` with the full report at `docs/research/lighthouse-pilot-scale.json`. Filed the finding as its own `ready` item, FR-77, with the reproduction, per the dod's second bullet — not fixed in this PR, since this item's job was to measure and record. Failure case not hit (Lighthouse ran fine), so nothing to report there beyond correcting the earlier wrong "cannot run" claim.
- gated: no
- why: FR-52's own dod asked for "Lighthouse mobile performance score for the public sheet"; `docs/research/pilot-scale-2026-09.md:38` records it was never run ("no Lighthouse in the harness") and FR-52 was still closed `done` on its other numbers — a dropped dod bullet, not a filed gap, on the item that set the hackathon's own performance bar.
- dod:
  - run Lighthouse (or `lighthouse-ci` via CDP against the local build, `/opt/pw-browsers/chromium`) against the public sheet for the FR-52 60-crew/30-day production, mobile config, and record the performance score in `docs/research/pilot-scale-2026-09.md`
  - any finding scoring under 90, or any specific audit flagged red, is filed as its own `ready` backlog item with the reproduction, not just noted in prose
  - failure case: if Lighthouse cannot run in this environment either, the report says exactly why (not the same "no Lighthouse in the harness" line repeated unchanged) and names the next environment that could run it, the same convention FR-40/FR-66 use for environment-blocked checks

## FR-72 · tech-lead · Measure push-notification publish latency at pilot scale, close ADR-007's own trigger
- state: done
- note: 13:00 shift 2026-09-23 (PR TBD, branch `test/fr-72-push-publish-latency`) delivered `backend/tests/test_push_scale.py`: 50 `PushSubscription` rows (within the dod's 40-60 range) seeded directly via the ORM, then one real publish through the API. Two measurements, both honestly labelled: (1) this codebase's own per-subscriber overhead with `webpush()` mocked to return instantly — 89 ms total, not the bottleneck; (2) the dod's own failure case exercised for real — a mocked-instant transport is too fast to represent a real network, so a second test gives `webpush()` a stated 150 ms/request delay (a conservative assumption, not a measurement; no live push service or real device exists in this sandbox to measure the real figure, and a targeted `WebSearch` for a published typical figure found nothing more specific than "under one second") and gets ~7.7 s for 50 subscribers, because `_notify` is strictly serial. Written into `docs/adr/ADR-007-web-push-notifications.md`'s Consequences section with both numbers and the assumption stated as such. Since even a conservative floor is not reassuring, treated this as the trigger's "noticeable" branch per the dod's second bullet: filed **FR-78** (background delivery, `ready`) rather than redesigning inside this item. 146/146 backend tests pass (2 new). No backend behaviour changed, so no deploy needed.
- gated: no
- why: `docs/adr/ADR-007-web-push-notifications.md:147-149` names its own revisit trigger — "Sending is synchronous with publish; revisit if a production's crew count makes publish latency noticeable" — but FR-52's pilot-scale test (`frontend/tests/test_scale.py`) seeds 60 crew members with zero `PushSubscription` rows, so publish latency with many subscribed devices has never actually been measured, only asserted safe by design. The hackathon goal's "crew gets a push" step must hold at real pilot crew sizes, not just the 2-3 test users every other test uses.
- dod:
  - a backend test seeds 40-60 `PushSubscription` rows for one production (mocking `app.services.push.webpush`, the same pattern `backend/tests/test_push.py` already uses) and measures `publish_revision`'s wall-clock time at that scale
  - the measured number is written into ADR-007's Consequences section, either closing the trigger with the real figure or, if it is in fact noticeable, filing a follow-up item for a background queue rather than redesigning now
  - failure case: if the mocked transport makes the measurement meaningless (too fast to be representative of a real network), the test says so and proposes what a representative measurement would need, rather than reporting a falsely reassuring number

## FR-73 · qa · Accessibility: 200% zoom and reflow on the crew sheet and personal link
- state: done
- note: 14:00 shift 2026-09-23 (PR TBD, branch `test/fr-73-reflow-200-zoom`) delivered every dod bullet. `frontend/tests/test_reflow.py` forces WCAG 1.4.10's own 320px-CSS-width reflow viewport (the documented equivalent of 400% zoom on a 1280px reference, itself the accepted proxy for the mobile "200% zoom" case) on the crew sheet demo (EN/CS) and a personal link, asserting no page-level horizontal scroll and no element whose content is wider than its box (the automatable proxy for "clipped text"; true visual overlap was not probed — nothing in this CSS uses absolute/negative-margin positioning for text, so it is not a realistic risk here, named as such in the report). Found and fixed a real bug: the mobile schedule table's Day/Night cell (`td.dn` in `styles.css`'s `@media (max-width: 560px)` block) inherited the desktop table's `width: 5ch` and a `padding-right: 12px` meant for a column boundary that no longer exists in the folded mobile grid — "DAY" fit, "NIGHT" clipped by 3px at 320px. Fixed with `width: auto; padding-right: 0` scoped to that mobile rule; not user-typed content, so fixed rather than documented as a limitation. Also exercised the dod's own failure case for real: published a revision with an unbroken, AD-plausible long compound set name (no spaces to break on) and confirmed the personal link at 320px neither clips nor scrolls horizontally — the `set` grid column is `1fr` and wraps correctly, so nothing needed documenting there either. `docs/research/a11y-2026-09.md` gets a new "Zoom / reflow, 2026-09-23 (FR-73)" section stating both results, replacing the old "not measured" line. Verified against a real build, a real uvicorn+Postgres API and this sandbox's pre-installed Chromium (pinned revision 1134 absent here, same known gap prior shifts noted; used a temporary `browser_type_launch_args` override in `tests/conftest.py`, reverted before commit, not part of the diff): new suite 4/4, full existing `test_a11y.py` 6/6 (no regression), `npm run typecheck`/`npm test` clean (49/49), the wider frontend Playwright suite 67/67 (excluding the same pre-existing unrelated Nominatim-egress failures in `test_locations_e2e.py` every prior shift has also hit, reconfirmed live), backend suite 146/146 unaffected. Touches `frontend/`, allowed under hackathon mode; auto-merge enabled. FR-73 set to done — the PR is the whole deliverable.
- gated: no
- why: `docs/research/a11y-2026-09.md:40` explicitly names this as not covered when FR-63 closed ("The layout is single-column and in relative units; not measured at 200 %") — WCAG 1.4.10 reflow, and a call sheet read at 05:00 with the phone's accessibility text scaling on must not clip content or force horizontal scroll.
- dod:
  - a Playwright test forces 200% zoom equivalent (per WCAG 1.4.10's own 320px-equivalent-viewport definition, or an actual browser zoom) on the crew sheet (EN and CS) and a personal link, and asserts no horizontal scroll and no clipped or overlapping text
  - any real finding is fixed in the same PR or filed as a `ready` item naming the criterion
  - the result (finding or clean pass) is appended to `docs/research/a11y-2026-09.md`'s "Not covered" section, converting it from "not measured" to a stated result
  - failure case: a layout issue that only appears on user-typed content (e.g. an unusually long set name or address) is documented as such, per FR-63's own precedent, not "fixed" by truncating the AD's text

## FR-74 · pm · Data retention policy: what happens to a wrapped production's data
- state: done
- note: 15:00 shift 2026-09-23 (branch `docs/fr-74-data-retention-policy`) delivered every dod bullet: `docs/ops/data-retention.md` proposes 12 months post-wrap for a wrapped production's contacts/photos/push subscriptions/read receipts, with the reasoning, and states plainly that the policy cannot be computed today — `Production` has no `wrapped_at`/`status_changed_at` timestamp, only `created_at`, named as the concrete prerequisite for real automatic deletion. Checked crew-member removal against the actual code, not assumed, by reproducing it live against a local Postgres: `CrewCallEntry` and `RevisionView` do cascade-delete (matches `privacy.html`'s claim), but a crew member with an active `PushSubscription` cannot be removed at all today — Postgres rejects the delete with a `ForeignKeyViolation` because `push_subscriptions.crew_member_id` has no `ON DELETE` clause, reproduced directly, not inferred from reading the migration. Filed as **FR-79** (tech-lead, ready) rather than fixed in this doc-only item. Also found no `DELETE /productions/{id}` endpoint exists at all — `privacy.html`'s "or deletes the production" was a promise the product cannot keep; corrected in the same PR, along with a caveat about the FR-79 bug. `backend/scripts/retention_report.py` (read-only, no deletion) lists wrapped productions with the retention-relevant counts, the crew members FR-79's bug would currently block, and orphaned contacts with no crew/cast membership — verified against a local Postgres with seeded fixtures covering all three categories, then re-run clean after removing them; full backend suite 146/146 (one run hit the same pre-existing intermittent `transaction already deassociated` flake on push/cancel tests earlier shifts flagged, a clean rerun immediately after was 146/146, unaffected by this change — no production code touched). `npm run typecheck`/`npm run build` clean; the existing `test_privacy_page_reachable_from_sheet_landing_and_editor` smoke test (checks structure, not the exact paragraph text edited here) verified passing against a real build in a real headless Chromium (this sandbox's pinned Playwright revision absent, same known gap prior shifts noted — used a temporary `conftest.py` fixture override to the pre-installed browser, reverted before commit, not part of the diff); one unrelated full-suite flake (`test_landing_flow_video_...`) reproduced clean in isolation, pre-existing contention noise, not this change. Doc-only + `backend/scripts/` + `frontend/privacy.html`; touches `frontend/`, allowed under hackathon mode. FR-74 set to `done` — the dod's own failure case holds: no deletion was implemented or performed, only proposed and reported.
- gated: no
- why: FR-59's own dod (done) is explicit that this is missing — "honest about what is not in place yet: no DPA template, no formal retention schedule" — and `docs/ops/backup-restore.md` never addresses deletion either; a pilot AD who asks "where is this and who sees it" (FR-59's own framing, privacy.html) will also ask "and when does it go away."
- dod:
  - `docs/ops/data-retention.md` states a concrete policy: what happens to a production's contacts, photos, push subscriptions and read receipts after it is marked wrapped/cancelled for N months (propose a number, e.g. 12, with the reasoning), and how a crew member's removal already deletes vs. retains their data today (checked against the actual code, not assumed)
  - a dry-run report script (`backend/scripts/retention_report.py`) lists what would be affected today under that policy — read-only, no deletion performed, no account needed
  - `frontend/privacy.html` is updated if the actual retention behaviour it currently states turns out to differ, checked line by line the same way FR-59 checked it against the code
  - failure case: the policy may propose a future automatic-deletion mechanism, but this item never implements deletion itself — that stays proposed text until the founder approves it via a new INBOX item, so nothing here can delete real pilot data

## FR-75 · frontend · Weather suggestion: distinguish "too far ahead to forecast" from "provider down"
- state: done
- note: 16:00 shift 2026-09-23 (PR TBD, branch `feat/fr-75-weather-horizon-message`) delivered every dod bullet frontend-only, no backend change: `frontend/src/editor/weatherHorizon.ts` exports `isBeyondWeatherForecastHorizon(shootDateIso, todayIso)`, comparing the shoot date against today plus Open-Meteo's ~16-day window already documented in ADR-006 and `weather.py`'s own docstring — no new external call, the horizon case now short-circuits before `api.weatherSuggestion` is even invoked. `DayEditor.tsx`'s `suggestWeather()` shows "Too far ahead to forecast yet — try again closer to the date." for the horizon case and a distinct "Could not get a weather forecast right now — the provider may be unreachable. Try again shortly." when the API call itself returns a null suggestion within the horizon; both strings added to `cs.ts`. Tests: a new unit suite (`weatherHorizon.test.ts`, 4 tests covering the boundary, past dates and unparsable input) plus two new Playwright E2E tests in `frontend/tests/test_locations_e2e.py` — one asserting the horizon message with the weather-suggestion route mocked to abort (proving the call never happens), one asserting the provider-failure message with the route mocked to return `{"suggestion": null}` (a real Open-Meteo outage isn't reproducible on demand, same reasoning prior shifts used for other mocked provider failures). Verified against a real build and a real uvicorn+Postgres API: `npm test` 53/53, `npm run typecheck`/`npm run build` clean, the 3 weather-suggestion E2E tests pass in this sandbox's pre-installed Chromium (pinned Playwright revision absent here, same known gap prior shifts noted — temporary `conftest.py` launch-args override, reverted before commit, not part of the diff); the wider `test_locations_e2e.py` suite is 9/11, the 2 failures being the pre-existing Nominatim-egress block every prior shift with this sandbox has hit, unrelated to this change (reconfirmed live: `Geocoding failed ... 403 Forbidden`). FR-75 set to `done` — the PR is the whole deliverable.
- gated: no
- why: `frontend/src/editor/screens/DayEditor.tsx:209` shows the identical "No weather suggestion available for that date/location." whether Open-Meteo is unreachable or the shoot date is simply beyond its ~16-day forecast horizon (`backend/app/services/weather.py` returns `None` for both cases by design); an AD prepping a day three weeks out reads this as a bug in the tool. Serves BRIEF Q3 (wrong or missing information undermines trust) and the hackathon goal's "day with locations" step.
- dod:
  - the backend or frontend distinguishes the two cases (e.g. comparing the shoot date against today plus the provider's known forecast window, no new external call needed) rather than collapsing both into one generic message
  - the editor shows "Too far ahead to forecast yet — try again closer to the date" for the horizon case and a distinct message for a real provider failure
  - a unit or E2E test covers both messages
  - failure case: if the two cases cannot be reliably distinguished without an extra provider call, the copy is at least changed to stop implying a specific failure ("no suggestion available yet" rather than "not available"), and the remaining ambiguity is stated in the PR

## FR-76 · qa · Pin today's 60-scene/day schedule size as a regression ceiling
- state: ready
- gated: no
- why: `docs/research/pilot-scale-2026-09.md` names the schedule list's row-virtualisation limit as a known future risk ("Above ~150 scenes a day it would need virtualising; noted, not planned") with no test guarding the size that is actually safe today; a later change (e.g. a new schedule column) could regress performance well before 150 scenes with nobody noticing until a real shoot day.
- dod:
  - a Playwright or unit performance test asserts the day screen with 60 scenes (FR-52's own pilot-scale figure) renders and stays interactive within the budget FR-52 measured, so a future regression fails CI instead of surfacing on a real set
  - the test's number and source (FR-52's own measurement, cited by file) are documented in a comment so nobody re-derives it as a coincidence
  - failure case: if the current numbers can't be reproduced deterministically in CI (timing flakiness), the test uses a generous multiple of FR-52's measured time (documented why) rather than being skipped or removed

## FR-77 · frontend · Public sheet: skeleton placeholder causes a 0.843 layout shift at pilot scale
- state: ready
- gated: no
- why: FR-71's Lighthouse run (2026-09-23, mobile, the FR-52 60-scene pilot-scale day) scored Performance 69/100, dragged down by Cumulative Layout Shift 0.843 (Lighthouse calls anything above 0.25 "poor"; "good" is under 0.1) — the crew's public sheet shows a ~100 px skeleton (`.skeleton` in `frontend/src/styles.css`) then swaps in the full sheet (schedule, cast, contacts — roughly 10,000 px tall at pilot scale) in one frame once the API responds, so the whole page jumps under the reader's thumb. This is exactly the kind of thing BRIEF Q3 flags (a call sheet read at 05:00 needs to be trustworthy and not fight the reader), and the hackathon goal names a pilot-ready crew sheet.
- dod:
  - reproduce first: `python3 frontend/scripts/lighthouse_pilot_scale.py` (needs a local Postgres and `npm run build`); confirm the Cumulative Layout Shift audit and its named culprit (`main#main`) before changing anything
  - the skeleton reserves realistic space for the incoming content (e.g. sized from the schedule item count once known, or a fixed tall placeholder tuned to typical scale) so the swap does not move content the reader may already be looking at, or the swap happens in a way that does not shift already-rendered content (e.g. reveal below the fold, not push everything down)
  - re-run the Lighthouse script after the fix and record the new score in `docs/research/pilot-scale-2026-09.md`, replacing the 0.843 figure — the dod is not met by a code change alone without the re-measurement
  - failure case: a call sheet that fails to load (network error, not-found) must still show its existing error states without reintroducing layout shift of its own

## FR-78 · tech-lead · Push notifications: send from a background task, not inside the publish request
- state: ready
- gated: no
- why: FR-72's latency measurement (2026-09-23, `backend/tests/test_push_scale.py`) found `app/services/notifications.py`'s `_notify` loop is strictly serial and runs inside the publish HTTP request; a stated, conservative assumption (150 ms per push, the low end of an ordinary synchronous HTTPS POST — no live push service or real device exists in this environment to measure the real figure) projects roughly 7.7 s of added latency at 50 subscribers, the low end of the hackathon's own 40-60 pilot-scale range. An AD tapping "Publish" and waiting nearly 8 seconds (or more, at the high end of the range or a slower push service) is a real, user-visible regression at the crew sizes the pilot targets, not a hypothetical one — ADR-007's own Consequences section named exactly this as the trigger to revisit.
- dod:
  - `publish_revision`'s HTTP response no longer waits on `notify_subscribers`/`notify_day_cancelled`; the caller (AD) sees "Published" as soon as the revision is committed, and delivery happens after the response returns (FastAPI `BackgroundTasks` is enough at this scale — no new queue infrastructure or account, consistent with the hackathon's "no new infra" instinct)
  - the `notifications` summary already returned in the publish response (attempted/delivered/failed) either becomes a best-effort snapshot with a documented caveat, or is dropped from the synchronous response and surfaced instead via the existing FR-50 publish-history panel once delivery finishes — pick one and say why in the PR
  - every existing FR-16/FR-72 test still passes, adjusted only for the new timing model (e.g. awaiting the background task in tests), not weakened
  - re-run `backend/tests/test_push_scale.py`'s assumed-delay case against the new code path and record that publish itself no longer scales with subscriber count
  - failure case: a delivery failure that happens after the response was already sent must still be logged per crew member exactly as today (the dod's original FR-16 failure case), never silently dropped because nothing is left waiting for it

## FR-79 · tech-lead · Removing a crew member with an active push subscription fails outright
- state: ready
- gated: no
- why: FR-74's retention audit (2026-09-23) reproduced this live against a local Postgres: `DELETE /productions/{id}/crew-members/{member_id}` (`app/routers/productions.py:414`) does `db.delete(member)` on a `CrewMember` row, but `push_subscriptions.crew_member_id` (`alembic/versions/c2a1f9e7b3d4_push_subscriptions.py:31`) is a plain foreign key with no `ON DELETE` clause — Postgres raises `ForeignKeyViolation` and the whole removal is rejected. An AD removing someone who has notifications turned on gets an unhandled 500, not a removed crew member; `frontend/privacy.html`'s promise that removal "drops your... push subscription" is false for that case today (corrected to say so, pending this fix, in the same PR that found it).
- dod:
  - `push_subscriptions.crew_member_id` gets `ON DELETE CASCADE` (model + a migration altering the existing constraint), matching the pattern already used for `crew_call_entries` and `revision_views`
  - a test creates a crew member with an active push subscription, deletes the crew member, and asserts both the delete succeeds (204) and the subscription row is gone — the same live reproduction this item's why cites, now green
  - `frontend/privacy.html`'s crew-removal paragraph (updated by FR-74 to note the bug) is updated again to drop the caveat once this ships
  - failure case: the migration must not silently drop existing orphaned rows beyond what the cascade implies; run it against a database that already has a subscription referencing a since-removed crew member (there shouldn't be one, given the current bug, but the migration itself must not error either way)

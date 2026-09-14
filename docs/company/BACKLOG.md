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
- state: ready
- gated: no
- why: "in everyone's pocket" needs one tap: the AD sends a link, the crew opens it, no typing of IDs or API URLs
- dod:
  - viewer accepts `?sheet=<id>&api=<base>` and loads without showing the lookup form (done 2026-09-14, fix/pwa-root-shows-demo); the editor shows the link (done, FR-17) and a QR code after publishing
  - the link survives a hot revision: reopening it shows the current revision, and a visible "REV B replaces A" note
  - failure case: a link to a call sheet that no longer exists or is not public shows a clear message, not a spinner

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
- state: blocked
- gated: no
- why: a crew member opens the link for one number, their own call time; today the sheet is the same for everyone (BRIEF Q3: wrong or missed call times; Q7: the wedge is the crew's pocket). Founder request 2026-09-14.
- dod:
  - each crew member gets a personal link (token per CrewMember, not per person globally) that renders their name, department, position, personal call and pickup at the top, then the full sheet
  - the department's own notes and HoD are shown before the rest; unrelated departments are collapsed, never hidden
  - backend: CrewMember gains a per-production personal token and an endpoint that resolves it; CastCallEntry already holds per-person times
  - Playwright: two personal links for the same sheet show different "your call" blocks
  - failure case: a personal link that no longer matches a crew member shows the general sheet with a clear note, not a 404 that strands someone at 05:30
- blocked-until: FR-10 (editor) and FR-12 (auth model decided), because the personal token design must match the auth ADR

## FR-16 · frontend · Notifications on publish and revision
- state: blocked
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
- state: blocked
- gated: no
- why: an AD publishes, a coordinator edits, a department head sees and annotates their department, everyone else reads; one shared token cannot express that. Founder request 2026-09-14; builds on FR-12.
- dod:
  - docs/adr/ADR-005-roles.md: roles `ad` (edit + publish), `coordinator` (edit drafts), `hod` (read all, edit own department notes), `crew` (read own personal sheet); roles are per production, one person can differ across productions
  - enforcement in the API (dependency that resolves user + production role), with tests: hod cannot publish, coordinator cannot publish, crew cannot read drafts
  - the editor shows only what the role may do; the viewer is unchanged for crew
  - failure case: a user with no role on a production gets 403 with a message naming the production, and nothing leaks about its existence beyond the name they already have
- blocked-until: FR-12

## FR-7 · security · Fix three findings from the founding commit review
- state: ready
- gated: no
- why: an automated security review of commit 81e9fc4 found a hardcoded dev token default in backend/app/config.py, stored XSS in frontend/index.html (API data rendered via innerHTML without escaping), and forgeable audit fields in backend/app/services/call_sheets.py
- dod:
  - config.py has no default bearer token; the app refuses to start without FILMRUNNER_API_BEARER_TOKEN outside development (done 2026-09-14, feat/fly-supabase-hosting, backend/tests/test_config.py)
  - index.html renders every API string via textContent or an escape helper; a test injects `<img onerror>` into a schedule item and asserts it is shown as text (done 2026-09-14 in feat/github-pages-demo, test_schedule_text_is_not_interpreted_as_html)
  - audit fields (created_by, published_at) are set server-side from the authenticated caller and the clock, never from the request body; a test sends spoofed values and asserts they are ignored (done 2026-09-14 with FR-12, backend/tests/test_auth.py)
  - failure case: if a fix would break the offline cache format, the PR says so and bumps the cache version instead of silently changing shape

## FR-9 · frontend · Offline-honest status when the service worker serves from cache
- state: ready
- gated: no
- why: verified 2026-09-14 on the live URL: after going offline and reloading, the app said "Live data" because sw.js answered the fetch from cache; the thesis is offline-honest, so this is a product bug, not cosmetics
- dod:
  - sw.js marks cache-served responses (e.g. a custom header or a wrapped Response) and index.html shows the cached-copy status with the original fetch time when it sees the mark
  - Playwright test: load once online, go offline, reload, assert the status says cached and shows a timestamp
  - failure case: if the mark is missing (older service worker still active), the app must not claim "live"; it says "unknown freshness" rather than guessing

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
- state: in-progress
- gated: no
- why: there is no constitution; every other item needs one to justify itself
- dod:
  - each open question in BRIEF.md has an owner and a concrete way it gets answered
  - the June 2026 brief (docs/reference/PRODUCT_BRIEF-2026-06.md) is read and its claims are listed as hypotheses, not facts
  - failure case: a hypothesis we cannot test within a month is marked "parked", not deleted or silently believed
- note: v0.1 shipped (BRIEF.md). Dod bullet 2 is partly blocked — `PRODUCT_BRIEF.md` is not present in this repo or reachable from the routine's environment, so its claims could not be read directly; BRIEF.md now says so explicitly and lists only reconstructed, clearly-unverified hypotheses. Closing this fully needs the founder to add the source document to the repo.

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
- state: blocked
- gated: no
- why: outreach and landing need one sentence of positioning that survives contact with an AD
- dod:
  - docs/marketing/positioning.md with alternatives considered and the chosen one, grounded in FR-1 and FR-2 findings
  - blocked until FR-1 and FR-2 are done
  - failure case: if FR-2 shows a competitor already owns the chosen position, the draft says so and proposes another, rather than ignoring it

## FR-4 · tech-lead · ADR-001: stack of the skeleton
- state: in-progress
- note: frontend half decided and written 2026-09-14 (docs/adr/ADR-001-frontend-stack.md, React + Vite + TS). Remaining: the backend half (why FastAPI + Postgres over the old Next.js + Supabase, what the old repo had that this lacks and when to port).
- gated: no
- why: the restart from Next.js + Supabase to FastAPI + vanilla PWA must be a recorded decision, not an accident
- dod:
  - docs/adr/ADR-001-stack.md states the options (keep old repo, this skeleton, hybrid), the choice, and the consequences
  - it lists what the old repo had that this one lacks (auth, SSO scaffold, budget, scheduling) and when each would be ported
  - failure case: if a hard requirement in BRIEF.md later contradicts the choice, the ADR names the trigger to revisit rather than being rewritten

## FR-5 · tech-lead · Security and QA gate checklist
- state: ready
- gated: no
- why: gates exist as roles in TEAM.md but not as a checklist anyone can run
- dod:
  - docs/gates/pre-merge-checklist.md with security items (secrets, auth on every non-public route, input validation, dependency pins) and QA items (tests for the change, failure case covered, CI green)
  - the PR template references it
  - failure case: a PR that skips the checklist is visible as such in the template, not silently merged

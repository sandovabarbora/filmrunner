# Backlog

Ordered by priority; the founder reorders. Grammar in TEAM.md.

## FR-8 · tech-lead · Hosted API and database for the PWA (second half of the demo deployment)
- state: in-progress
- note: first half done 2026-09-14 (GitHub Pages, `?demo=1`, pages.yml, PR #17). This item is now the API: ADR-002, fly.toml + Dockerfile release step for alembic, Supabase Postgres connection via platform secrets (Postgres only; no Supabase-specific schema features), CORS for the Pages origin, INBOX items for the Fly and Supabase accounts. The PWA must be able to load a real call sheet by id from the hosted API. Founder chose Supabase over Neon on 2026-09-14 (DECISIONS.md).
- gated: partial
- why: showing an AD a call sheet that works on their own phone with no signal is stronger evidence than any interview question; the PWA needs HTTPS and a public API to exist outside localhost
- dod:
  - docs/adr/ADR-002-demo-hosting.md: frontend on GitHub Pages (done), backend on Fly.io (or Railway) from the existing Dockerfile, Postgres on Supabase used as plain Postgres; alternatives and costs stated; migrations run as a release step, not on every boot
  - deploy configs committed (fly.toml, Pages config, GitHub Actions deploy job triggered on main) with secrets read from the platform, never from the repo
  - INBOX items for every account, domain, or payment the founder must create; the routine never creates them
  - a seed script that loads one realistic demo production and call sheet so the URL shows something on first open
  - failure case: if the service worker does not register on iOS Safari over the deployed HTTPS URL, the ADR records it as a blocker for the demo and proposes the fallback (install banner off, plain web link) instead of shipping a demo that silently fails on the phones ADs actually carry

## FR-10 · frontend · Minimal AD editor: create a call sheet and publish a revision from a phone
- state: ready
- gated: no
- why: the wedge is "AD publishes, crew receives"; today a call sheet can only be created with curl against the API, so nothing is usable by a real AD
- dod:
  - a React route/screen in frontend/ (ADR-001 stack) lets an AD pick or create a production, create a shoot day, add schedule items (scene, int/ext, day/night, set, pages in eighths), set crew call and safety notes, and publish; publishing again creates the next revision letter through the existing API
  - works on a phone screen width first (the AD's Tuesday is on set, not at a desk); desktop is a bonus
  - the design is discussed in a short docs/adr/ADR-003-editor.md before code: which API calls, what is saved when, what happens when the network drops mid-edit
  - Playwright test against the real API: create, publish A, publish B, assert the viewer shows REV B and the schedule
  - failure case: losing the network while editing must not lose the draft; the draft is kept in IndexedDB and the app says it is unsaved

## FR-11 · frontend · Share link and QR for the crew
- state: ready
- gated: no
- why: "in everyone's pocket" needs one tap: the AD sends a link, the crew opens it, no typing of IDs or API URLs
- dod:
  - viewer accepts `?sheet=<id>&api=<base>` and loads without showing the lookup form (done 2026-09-14, fix/pwa-root-shows-demo); the editor shows the link and a QR code after publishing
  - the link survives a hot revision: reopening it shows the current revision, and a visible "REV B replaces A" note
  - failure case: a link to a call sheet that no longer exists or is not public shows a clear message, not a spinner

## FR-7 · security · Fix three findings from the founding commit review
- state: ready
- gated: no
- why: an automated security review of commit 81e9fc4 found a hardcoded dev token default in backend/app/config.py, stored XSS in frontend/index.html (API data rendered via innerHTML without escaping), and forgeable audit fields in backend/app/services/call_sheets.py
- dod:
  - config.py has no default bearer token; the app refuses to start without FILMRUNNER_API_BEARER_TOKEN outside development (done 2026-09-14, feat/fly-supabase-hosting, backend/tests/test_config.py)
  - index.html renders every API string via textContent or an escape helper; a test injects `<img onerror>` into a schedule item and asserts it is shown as text (done 2026-09-14 in feat/github-pages-demo, test_schedule_text_is_not_interpreted_as_html)
  - audit fields (created_by, published_at) are set server-side from the authenticated caller and the clock, never from the request body; a test sends spoofed values and asserts they are ignored
  - failure case: if a fix would break the offline cache format, the PR says so and bumps the cache version instead of silently changing shape

## FR-12 · tech-lead · Real auth: per-production access instead of one shared dev token
- state: ready
- gated: no
- why: the editor cannot go to a real AD while every write is protected by a single token in an env var
- dod:
  - docs/adr/ADR-004-auth.md compares Supabase Auth (magic link, JWT verified in FastAPI), a per-production secret link, and a hand-rolled magic link; picks one for the pilot with the reason; the data model must stay plain Postgres (no RLS as business logic)
  - implementation with tests: unauthenticated writes 401, a token for production A cannot touch production B, public read stays public
  - failure case: a leaked per-production token can be rotated without losing data, and the test proves the old one stops working

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

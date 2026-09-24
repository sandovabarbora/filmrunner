# Competitive teardown: call-sheet tools

FR-2. Role: pm. Date checked: 2026-09-14.

## Method and a limitation to disclose up front

This shift's network egress proxy blocks direct fetches of every vendor
domain tried (studiobinder.com, sethero.com, croogloo.com, g2.com, ep.com).
`WebFetch` returned `EGRESS_BLOCKED` for all of them. Everything below
therefore comes from `WebSearch` result snippets — which do quote and
summarize the vendor's own pages and third-party listings (G2, Capterra,
GetApp, app-store listings) — not from this shift reading the full page
itself. Every claim is cited with the URL `WebSearch` surfaced and the date
checked (2026-09-14). Anything the snippets did not cover clearly is marked
**unverified** rather than guessed, per FR-2's failure case. A future shift
with working `WebFetch` (or a founder session) should re-verify the
marked items directly against the vendor pages.

## StudioBinder

- **Build**: call sheet fields (schedule, locations, cast, crew) pull
  automatically from the rest of the StudioBinder project; a drag-and-drop
  builder lets you show/hide/reorder elements and add branding
  ([studiobinder.com/call-sheet-app](https://www.studiobinder.com/call-sheet-app/), checked 2026-09-14).
- **Revise**: StudioBinder keeps one "living" call sheet — the latest
  revision always loads, with a revision history you can load prior server
  versions from; a big change can be pushed as a resend with a special
  announcement message ([support.studiobinder.com revision history](https://support.studiobinder.com/en/articles/10076109-how-to-load-a-server-version-from-revision-history), [studiobinder.com blog](https://www.studiobinder.com/blog/create-better-call-sheet-with-free-call-sheet-template/), checked 2026-09-14).
- **Distribute**: sent by SMS and email; delivery is tracked in real time —
  bounced, viewed, and confirmed states per recipient, from a central
  dashboard ([studiobinder.com/call-sheet-app](https://www.studiobinder.com/call-sheet-app/), checked 2026-09-14).
- **View offline**: an offline version is described by a third-party
  review as "in the pipeline" ([musicgateway.com review](https://www.musicgateway.com/blog/filmmaking/studiobinder-production-software-review), checked 2026-09-14) — i.e. **not offline-capable today**; recipients view a
  web page/PDF that assumes connectivity. **Unverified** directly against
  StudioBinder's own docs (page blocked); treat this as a hint, not
  confirmed fact, until re-checked.
- **Pricing**: seat-based, from roughly $29/seat/month as of July 2026
  per a third-party comparison ([sethero.com comparison guide](https://sethero.com/blog/best-call-sheet-software-comparison/), checked 2026-09-14); StudioBinder's own
  marketing says core call-sheet access is free on every tier including
  Free, with paid tiers adding features/content
  ([studiobinder.com/call-sheet-app](https://www.studiobinder.com/call-sheet-app/), checked 2026-09-14). Exact current tier prices are
  **unverified** — the pricing page itself was blocked.
- **Buyer**: implied production-company/production-office seat licensing
  (per-seat pricing, Teams/Enterprise tiers) rather than an individual AD
  buying alone. **Unverified** in detail.

## Yamdu

- **Build/revise**: users plan sessions/appointments/callbacks and Yamdu
  compiles the information into exportable/printable call sheets, schedule
  planners, and inventory reports; a "reimagined call sheet creator" is
  advertised as a recent feature update ([yamdu.com blog](https://yamdu.com/en/blog/yamdus-all-new-call-sheet-creator/), [capterra.com](https://www.capterra.com/p/186025/Yamdu/), checked 2026-09-14).
- **Distribute**: a separate "Yamdu Notifier" mobile app (iOS/Android)
  surfaces the latest call sheets, announcements, calendar events and
  travel info, and lets crew navigate contact lists
  ([apps.apple.com Yamdu Notifier](https://apps.apple.com/us/app/yamdu-notifier/id1004501663), [play.google.com](https://play.google.com/store/apps/details?id=com.yamdu.app.mobile&hl=en), checked 2026-09-14).
- **View offline**: **unverified** — search results describe what the
  Notifier app shows but not whether it caches data for offline viewing.
- **Pricing**: a Flex tier starting at $45/month plus $22/additional user,
  and a Core tier at $265/month for up to 20 users with unlimited projects
  ([g2.com pricing summary via search](https://g2.com/products/yamdu/pricing), checked 2026-09-14). Not confirmed against Yamdu's own site
  (blocked).
- **Buyer**: pitched at producers, directors, and production managers
  running projects with many moving parts, i.e. the production office, not
  an individual crew member ([capterra.com](https://www.capterra.com/p/186025/Yamdu/), checked 2026-09-14).

## SetHero

- **Build**: drag-and-drop call sheet editor with error detection,
  automatic weather, overtime calculations, and templates by production
  type ([sethero.com comparison guide](https://sethero.com/blog/best-call-sheet-software-comparison/), checked 2026-09-14).
- **Distribute**: call sheets go out by email and text; SetHero's own
  positioning is that cast/crew view everything from a phone's browser
  with **no app download required**
  ([sethero.com comparison guide](https://sethero.com/blog/best-call-sheet-software-comparison/), checked 2026-09-14).
- **View offline**: the "no app, browser only" design implies connectivity
  is assumed at view time; no offline/caching claim found. **Unverified**
  directly (FAQ page blocked) — flagged rather than assumed either way.
- **Revise**: a centralized contact system and mobile-optimized view are
  named; explicit revision-history/version-tracking behavior comparable to
  StudioBinder's was **not found** in the available snippets — **unverified**.
- **Pricing**: two models — per-project pricing (one-off shorts/features)
  and monthly subscriptions starting at $19/month that scale with
  project count/size ([g2.com via search](https://www.g2.com/products/sethero/pricing), [help.sethero.com pricing article via search](http://help.sethero.com/en/articles/1513627-how-do-the-pricing-plans-work), checked 2026-09-14). Exact tier breakdown is
  **unverified** — sethero.com/pricing itself was blocked.
- **Buyer**: producers/ADs running individual productions (project-based
  pricing fits a per-shoot buyer, not just a standing production company).

## Movie Magic Scheduling (Entertainment Partners)

- **Build**: desktop scheduling software — script breakdown, stripboards,
  multi-episode/multi-unit schedules with conflict detection; call sheets
  and crew reports are generated from the schedule
  ([storyflow.so 2026 roundup](https://storyflow.so/blog/best-film-scheduling-software-2026), [musicgateway.com](https://www.musicgateway.com/blog/film-industry/movie-magic), checked 2026-09-14).
- **Revise**: schedule and script-revision syncing is a named feature;
  granular call-sheet-level revision tracking (vs. schedule revisions) was
  **not found** in the available snippets — **unverified**.
- **Distribute**: primarily a desktop, offline-by-default tool — data is
  stored locally and PDFs are generated and distributed manually (e.g. by
  email); productions commonly pair it with a separate tool (StudioBinder,
  Studiovity) to get modern mobile call-sheet distribution
  ([studiobinder.com/movie-magic-scheduling-into-call-sheets](https://www.studiobinder.com/movie-magic-scheduling-into-call-sheets/), checked 2026-09-14).
- **View offline**: the *authoring* tool is desktop/offline by nature; the
  *distributed call sheet* itself is a static PDF, which is trivially
  viewable offline once downloaded but has none of the "always latest
  version" behavior StudioBinder/SetHero advertise. This is the one
  incumbent where offline viewing is a side effect of being a dumb PDF,
  not a designed feature.
- **Pricing**: $42.99/month per seat for Scheduling alone, roughly
  $86/month per person bundled with Movie Magic Budgeting
  ([musicgateway.com](https://www.musicgateway.com/blog/film-industry/movie-magic), checked 2026-09-14). Not confirmed on ep.com directly (blocked).
- **Buyer**: line producer / production coordinator role, licensed by
  Entertainment Partners per seat — a studio/production-company line item,
  historically the incumbent on larger union productions.

## Croogloo

- **Build/distribute**: positioned as a production-office distribution
  and communications platform: composes call sheets and sides, compares
  script revisions, and pushes them with no recipient limit; security
  features include watermarking, expiry dates, and access control on
  distributed files ([croogloo.com/features via search](https://croogloo.com/features/), checked 2026-09-14).
- **Revise**: script/sides comparison is named explicitly, implying
  built-in revision diffing — call-sheet-specific revision-history UI is
  **unverified** (features page blocked from direct read).
- **Distribute (tracking)**: distribution reporting shows when a call
  sheet lands, when it is opened, and who has not yet received it, plus
  text notifications on call-time changes — the most granular delivery
  tracking of the five tools researched ([croogloo.com/features via search](https://croogloo.com/features/), checked 2026-09-14).
- **View offline**: **unverified** — not addressed in the available
  snippets either way.
- **Pricing**: custom/quote-based overall; a lower-cost "Croogloo Kit"
  product starts at $19/month, while the studio-grade "Distribution Kit"
  is quote-only with indie/low-budget discounts available on request
  ([support.croogloo.com Kit pricing via search](https://support.croogloo.com/en/articles/10245800-croogloo-kit-pricing), [croogloo.com/pricing via search](https://croogloo.com/pricing/), checked 2026-09-14).
- **Buyer**: explicitly studio-grade — built for production offices on
  larger productions that need secure, tracked distribution (watermarking,
  access control), not a solo AD on a short ([search synthesis of croogloo.com](https://croogloo.com/), checked 2026-09-14).

## What this means for BRIEF.md's open questions

- **Q6 (what makes an AD switch)**: every incumbent above sells to the
  *production office* (producer, PM, line producer), not to the AD who
  actually assembles the call sheet day-to-day. If FR-3 interviews confirm
  the AD is not the budget holder, positioning and pricing need to target
  whoever approves the software line item, not the AD directly — matches
  BRIEF.md Q4's framing.
- **Offline is contested ground, not solved ground**: of five incumbents,
  only Movie Magic's exported PDF is offline-usable, and only as a side
  effect of being a static file with no live-update behavior. StudioBinder
  markets offline as "coming soon"; SetHero explicitly avoids an app in
  favor of a browser view (assumes signal); Yamdu and Croogloo's offline
  behavior could not be verified either way. A call sheet that is
  genuinely both live *and* offline-honest — the BRIEF.md wedge — is not
  something any researched incumbent currently and verifiably ships. This
  strengthens rather than undercuts the working hypothesis, but it rests on
  gaps in what could be verified this session, not on a confirmed absence
  in each vendor's own docs.
- **Displacement risk (Q6)**: StudioBinder and Croogloo both build
  delivery-tracking (open/confirm/bounce) as a core feature. Any MVP call
  sheet product needs at least read-receipt tracking to be taken seriously
  as a replacement, not just distribution.

## Re-verification pass (FR-83, 2026-09-24)

`scripts/reverify_desk_research.py`, run as a GitHub Actions job with open
egress (`.github/workflows/desk-research-reverify.yml`, runs #1/#2), fetched
the specific pages this doc names as blocked. None of it changes an
**unverified** marker to confirmed outright — every hit needs the caveat
below — but it narrows what the *next* re-verification pass needs to do:

- **StudioBinder pricing** (`app.studiobinder.com/pricing`): reachable (200,
  13 KB) for the first time — not vendor-blocked, just a client-rendered
  React app, so the raw HTML has no readable pricing digits. The exact tier
  figures are still **unverified**, but the next attempt needs a headless
  browser (e.g. Playwright), not a plain fetch.
- **StudioBinder mobile/offline**
  (`support.studiobinder.com/en/articles/1065638-is-there-a-mobile-or-tablet-app-available`,
  the specific support article for this claim, not previously cited):
  timed out on both runs. Still **unverified**, now for a different reason
  (timeout, not a 403) — worth one more attempt with a longer timeout.
- **Yamdu pricing** (`yamdu.com/en/pricing/`): reachable (200, 19 KB), but
  the script's `Flex` match was a false positive — a Tailwind CSS class
  (`flex flex-wrap`), not the Flex plan name. Also a client-rendered app.
  Still **unverified**.
- **SetHero pricing and FAQ** (`sethero.com/pricing/`, `sethero.com/faq/`):
  403 on both, from a GitHub Actions runner with open egress, not just this
  sandbox's own proxy — this looks like real bot protection (Cloudflare or
  similar) rather than a proxy-specific block. Still **unverified**; a
  future pass should try a browser-shaped request (real headers, JS
  execution) rather than a bare fetch.
- **Croogloo features** (`croogloo.com/features/`): now **404**, not merely
  blocked. The URL cited throughout this doc (2026-09-14) may have moved or
  been retired since. Flag this as a stale citation — a fresh `WebSearch`
  for Croogloo's current features page is needed before this doc's Croogloo
  claims can be re-sourced, rather than treating the 404 as "feature
  removed."
- **Movie Magic Scheduling pricing, monthly**
  (`ep.com/ep-store/movie-magic-scheduling-monthly/`): reachable, and its
  page JSON-LD names a price of **$29.99**, not the $42.99/month this doc
  cites from `musicgateway.com`. This is a real discrepancy, not a
  confirmation — the excerpt alone does not establish which specific
  product/tier that $29.99 belongs to (`ep.com`'s store template covers
  several Movie Magic products), so the original $42.99 figure is now
  **contradicted-or-unclear** rather than simply unverified; resolve which
  figure is current before citing either in positioning or pricing copy.
- **Movie Magic Scheduling pricing, annual**
  (`ep.com/ep-store/movie-magic-scheduling-annual/`): reachable, but its own
  meta description names **Movie Magic Budgeting**, not Scheduling — a sign
  this specific URL may be the wrong product page (or `ep.com` reuses one
  template's meta tag sitewide). Not usable as confirmation either way;
  still **unverified**, and the correct Scheduling-specific annual URL
  still needs to be found.

Full raw output (status, byte length, every substring match with its
excerpt) is in the job's own log and artifact; `docs/research/desk-research-reverify.json`
is regenerated on each run rather than committed, since it is a point-in-time
fetch, not a stable research artifact.

## Follow-up needed (cannot be done by this routine)

- Re-run this teardown with working `WebFetch`/browser access to read
  each vendor's pricing and product pages directly, and resolve every
  item marked **unverified** above.
- Confirm current-year (2026) pricing directly on each vendor site —
  several figures above come from third-party aggregators that may lag
  the vendor's own page.
- A headless-browser fetch (not a plain HTTP GET) for the client-rendered
  pages the 2026-09-24 pass found reachable but unreadable (StudioBinder,
  Yamdu); a fresh `WebSearch` for Croogloo's current features URL; and
  resolving the Movie Magic pricing discrepancy above.

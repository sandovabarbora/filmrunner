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
- **View offline** (confirmed 2026-10-06, FR-138 — see the resolution
  below): the original claim ("in the pipeline", a third-party review)
  was never confirmed against StudioBinder's own docs, only hinted at.
  Headless-rendered directly from StudioBinder's own help article
  ([support.studiobinder.com "Is there a mobile or tablet app
  available?"](https://support.studiobinder.com/en/articles/1065638-is-there-a-mobile-or-tablet-app-available),
  checked 2026-10-06, HTTP 200, full text read): "While StudioBinder does
  not currently offer a dedicated iOS or Android app, the platform is
  mobile-responsive on the recipient side. This means your crew can view
  and interact with call sheets they receive on their mobile devices,"
  with a note recommending "sticking to your computer" for full project
  management. This confirms directly, not as a hint, that there is **no
  native app** — only a mobile-responsive web view — which rules out the
  on-device caching an app would need for offline access. The article
  itself never uses the word "offline" and makes no claim either way
  about viewing without connectivity; the original "in the pipeline"
  wording is therefore **still unverified as a specific offline-viewing
  roadmap item** — this resolution confirms the weaker, adjacent fact
  (no app exists today) but does not confirm or deny that StudioBinder is
  building offline support. Treat "not offline-capable today" as
  consistent with the evidence (no app, a web view that is not described
  as working offline) rather than as directly stated by the vendor.
- **Pricing** (confirmed 2026-09-25, FR-90 — see the resolution below):
  headless-rendered directly from `app.studiobinder.com/pricing` itself, not
  a third-party comparison. The "For Small Teams" tab: Free ($0, "covering
  all of pre-production from scripting to call sheets" — free tier does
  include call sheets, confirming the earlier claim), **Starter $29/mo**
  (1 user, 50 GB), **Indie $49/mo** (2 users, 75 GB, marked "Most Popular"),
  **Professional $99/mo** (4 users, 100 GB) — all billed monthly, an annual
  toggle offers "SAVE 15%". The "For Organizations" tab adds Agency, Studio
  (20 users, 400 GB), and a custom-quote Enterprise tier. Every paid tier's
  feature list includes "Call Sheets" (Starter) or "Advanced Call Sheets"
  (Indie/Pro and up). The original $29/seat/month figure (a third-party
  comparison, checked 2026-09-14) is now confirmed directly against the
  vendor's own page — it is exactly the Starter tier's price, not a rough
  estimate.
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
  ([g2.com pricing summary via search](https://g2.com/products/yamdu/pricing), checked 2026-09-14). Not confirmed against Yamdu's own site — a
  headless-rendered read of `yamdu.com/en/pricing/` (FR-90, 2026-09-25, see
  the re-verification pass below) shows nothing to confirm or contradict
  this figure with: the page fully loads (26 rendered text lines) but
  contains zero pricing content, not even plan names — only navigation,
  a language switcher, and the footer. **Still unverified**, now for a
  different reason: the pricing page as currently built shows no prices at
  all to a plain page load, not that the content was hidden behind
  client-side rendering.
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
- **Pricing** (corrected 2026-09-25, FR-89 — see the resolution below): the
  vendor's own store pages price Scheduling alone (not bundled with
  Budgeting) at **$39.99/month regular, $29.99/month as a "limited time
  introductory price"**, and its annual subscription (12-month commitment)
  at **$279.88/year regular, $199.88/year introductory**
  ([ep.com monthly](https://www.ep.com/ep-store/movie-magic-scheduling-monthly/),
  [ep.com annual](https://www.ep.com/ep-store/movie-magic-scheduling-annual/),
  both JSON-LD product data plus visible page text, checked 2026-09-25). The
  previously cited $42.99/month and ~$86/month-bundled figures
  ([musicgateway.com](https://www.musicgateway.com/blog/film-industry/movie-magic), checked 2026-09-14) do not match either ep.com price and could not
  be reproduced from the vendor's own pages; treat them as a stale or
  incorrect third-party figure, not a second real tier.
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
  **unverified** (features page blocked from direct read, now confirmed
  404/gone, FR-87/135). FR-148 (2026-10-08) headless-rendered three
  Croogloo help-center articles found by FR-136 ("Technical Support"
  collection, "Distribution Drafts", "Adding Dailies to Call Sheet
  Distro") on the chance they addressed this; none of the three covers
  revision history or a call-sheet UI at all (troubleshooting/login,
  draft emails, and dailies-distribution-list management respectively —
  detail in `switching-cost-teardown.md`'s FR-148 section), so this claim
  stayed **unverified**, not resolved by that pass. FR-151 (2026-10-08,
  same day) re-searched with the differently-worded queries FR-148's own
  follow-up named — `WebSearch` for `Croogloo "version history" call
  sheet`, `Croogloo call sheet revisions site:support.croogloo.com`,
  `Croogloo "republish" OR "revise" call sheet crew`, `Croogloo "Archive
  Mode" documents`, and `croogloo.com call sheet revision "rev" change
  log feature` — plus a direct browse of the help center's own
  collections and search index (`support.croogloo.com/en/collections/…`,
  `site:support.croogloo.com call sheet`; direct `WebFetch` to
  `support.croogloo.com` is egress-blocked from this environment, same
  as every prior shift's finding, so `WebSearch`'s own index of that
  domain is the only reachable substitute). The collections browse
  surfaced the real top-level structure (Production Office, Documents —
  14 articles, Technical Support, Troubleshooting, Side Kit, Welcome to
  Croogloo) and several real articles never seen before this pass
  (`Distribution Drafts` — unlimited call-sheet drafts shared among the
  team, pre-send only; `Attaching a Call Sheet to Sides`; `Sides in 1-up
  & 2-up Format`; `Cast - Agent Pairing`; `FAQ - Troubleshooting`); none
  of them, by title or by the snippet text returned, addresses a
  published call sheet's revision/version history. This claim is now
  **unverified, exhausted the help-center and search avenues available
  to this routine** — a real answer needs either a Croogloo account
  (to read in-app UI directly) or a vendor statement using the words
  "revision" or "version history" that this pass's searches did not
  surface, not a further re-search with this routine's tools.
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

## Re-source attempt for the Croogloo stale citation (FR-87, 2026-09-25)

FR-83 flagged `croogloo.com/features/` as newly 404 and asked for "a fresh
`WebSearch` for Croogloo's current features page… before treating the 404
as feature removed." That search was run this shift, several ways
("croogloo.com features call sheet distribution", a site-structure query,
a navigation-focused query) — every one of them returns the exact same
dead URL as a top result, plus `croogloo.com/pricing/`,
`croogloo.com/compare-pricing/`, `croogloo.com/` (home) and several
`support.croogloo.com` help articles, all as live-looking snippets. This
looked at first like the page might genuinely still be there and only
blocked from this sandbox, so the re-verify job
(`scripts/reverify_desk_research.py` via `.github/workflows/desk-research-reverify.yml`,
open egress) was re-run today and, separately, temporarily extended to also
probe `https://www.croogloo.com/features/` (the www-prefixed host) in case
the bare domain was the actual problem. Both came back **404** from the
open-egress runner (run [36111762139](https://github.com/sandovabarbora/filmrunner/actions/runs/36111762139)
for the bare host, [36111869883](https://github.com/sandovabarbora/filmrunner/actions/runs/36111869883)
for the www probe on a throwaway branch, not merged). No other URL under
`croogloo.com/*` in any search result names a marketing "features" page —
the closest live pages are `/pricing/`, `/compare-pricing/`, and the
help-center collections (Scripts & Sides, Distribution), which document
individual actions, not a features overview.

**Conclusion: genuinely gone, not a fetch/proxy artifact** — Google's own
search index still surfaces the dead URL's cached title ("Features –
Croogloo") as if it were live, which is itself worth flagging: a future
re-verification pass should not treat a `WebSearch` hit on this exact URL
as confirmation it resolves, without an independent fetch. No live
replacement page was found. The call-sheet-specific revision-history claim
this citation supported (line ~123-125 above) stays **unverified** — not
guessed from the help-center articles, which describe scripts/sides
comparison, not a call-sheet revision UI specifically — per this item's own
failure case. Checked 2026-09-25.

## Resolution: Movie Magic Scheduling pricing discrepancy (FR-89, 2026-09-25)

FR-83 (2026-09-24) found `ep.com`'s own Movie Magic Scheduling monthly page
prices at $29.99, contradicting this doc's original $42.99/month citation
(from `musicgateway.com`, a third-party aggregator), and flagged it
**contradicted-or-unclear** without resolving which figure — or which
product/tier — was current.

This shift extended `scripts/fetch_page_text.py` to also extract a page's
JSON-LD `Product`/`Offer` block (the general script-stripping the rest of
that script does would otherwise discard it along with every other
`<script>` tag), then re-dispatched `.github/workflows/desk-research-reverify.yml`
from the feature branch with the two `ep.com` Scheduling pricing URLs plus
the general `ep.com/movie-magic-scheduling/` marketing page added
([run 36122876922](https://github.com/sandovabarbora/filmrunner/actions/runs/36122876922),
open egress, not this sandbox's blocked proxy):

- **Monthly** (`ep.com/ep-store/movie-magic-scheduling-monthly/`): JSON-LD
  names the product plainly **"Movie Magic Scheduling"** (Scheduling alone,
  not bundled with Budgeting — resolving FR-83's own open question about
  which product the store template covers), `price: "29.99"`,
  `priceCurrency: "USD"`. The page's visible text shows this as a
  **"Limited time introductory price"** of $29.99/month, struck through
  against a **regular price of $39.99/month**.
- **Annual** (`ep.com/ep-store/movie-magic-scheduling-annual/`): JSON-LD
  names the product **"Movie Magic Scheduling Annual Subscription"**,
  `price: "199.88"`. Its visible text shows the same pattern: $199.88/year
  introductory against a $279.88/year regular price, with a 12-month
  commitment required. This also resolves FR-83's separate flag that the
  annual page's meta description named Budgeting, not Scheduling — the
  JSON-LD product name (the more specific and reliable signal) confirms
  this page is genuinely the Scheduling annual subscription.
- **General marketing page** (`ep.com/movie-magic-scheduling/`): no price
  shown at all, only a "Get pricing" call-to-action — confirms the store
  pages above are the only place ep.com states a figure.

Neither ep.com page nor its JSON-LD ever states $42.99 or ~$86/month in any
form, for any tier or billing period. The original $42.99/month figure
(`musicgateway.com`, checked 2026-09-14) is therefore **not a different,
real tier** — it does not match ep.com's introductory price ($29.99), its
regular price ($39.99), or its bundled-with-Budgeting framing (ep.com's own
pages price Scheduling and Budgeting as fully separate products, each with
their own store page). Per this item's own failure case: the discrepancy is
resolved by preferring the vendor's own page over a third-party aggregator,
not by picking a number — the corrected pricing line above now cites
`ep.com` directly with both the introductory and regular figures, and notes
the earlier $42.99 citation as likely stale or incorrect rather than
silently dropping it.

## Rendered-page re-verification (FR-90, 2026-09-25)

FR-83 found StudioBinder's and Yamdu's pricing pages reachable but
client-rendered, so a plain `urllib` fetch (`reverify_desk_research.py`)
never saw their actual text. `scripts/render_pricing_pages.py`, run as a
GitHub Actions job with open egress (extending
`.github/workflows/desk-research-reverify.yml`, [run 36128372771](https://github.com/sandovabarbora/filmrunner/actions/runs/36128372771)),
drives real headless Chromium (Playwright) against each page instead and
extracts the rendered visible text — resolving FR-83's own "needs a headless
browser" flag for both.

- **StudioBinder pricing**: confirmed directly; see the corrected pricing
  bullet above. One methodological note worth recording: the page's *top*
  pricing cards render their dollar figures through an animated digit
  widget whose DOM exposes many stray single-digit lines under plain text
  extraction (e.g. `0 1 2 0 0 9 9` for a `$29`+something amount) — not
  usable at all. The real, clean figures came from a *second*, plainer
  "Compare Features" pricing table further down the same page, which
  renders `$29`/`$49`/`$99` as ordinary single text nodes. A future
  headless-render pass on a similarly-styled page should look past the
  first price display it finds if the digits don't parse cleanly, rather
  than conclude the page has no readable price.
- **Yamdu pricing**: rendered fully (not blocked, not timing out) but
  genuinely contains no pricing content — see the corrected bullet above.
  **Still unverified**, cause narrowed from "client-rendered" to "no
  pricing text present on this page at all as currently built".
- **SetHero pricing** (`sethero.com/pricing/`) and **FAQ**
  (`sethero.com/faq/`): both returned HTTP 202 with only 3 rendered text
  lines each (a holding/interstitial response, not the real page) — a
  different status than FR-83's 403s but the same real-bot-protection
  pattern (this is a GitHub Actions runner with open egress, not this
  sandbox's proxy). **Still unverified**; a future attempt would need a
  browser fingerprint or wait strategy this script's default 30s
  `networkidle` wait didn't clear.
- **SetHero's Exporting Data article**: see the resolution in
  `switching-cost-teardown.md` — confirmed, not just rendered.

## Re-verification pass (FR-135, 2026-10-06)

This doc's own "Follow-up needed" list (below, as it read before this
section) named four specific claims as the only ones left unresolved by
FR-83/87/89/90. This shift re-dispatched
`.github/workflows/desk-research-reverify.yml` unchanged on `main` (open
egress, not this sandbox's blocked proxy) and read the job log directly
([run 37441525900](https://github.com/sandovabarbora/filmrunner/actions/runs/37441525900)) —
no `WebSearch` snippet substituted for any of the four:

- **Yamdu pricing** (`yamdu.com/en/pricing/`): re-confirmed, no change
  since FR-83/90. The plain fetch's `Flex` substring match is still the
  Tailwind CSS class (`flex flex-wrap`), not the plan name; the headless
  render (`render_pricing_pages.py`) still shows the page fully loads (26
  rendered text lines) with zero pricing content, only navigation and a
  footer. **Still unverified**, same reason as before — nothing on the
  live page has changed in the eleven days since FR-90.
- **SetHero pricing and FAQ** (`sethero.com/pricing/`, `sethero.com/faq/`):
  re-confirmed, no change. Both the plain fetch (202, ~180 bytes) and the
  headless render (202, 3 rendered text lines) still return the same
  holding/interstitial response FR-83/90 found — real bot protection, not
  a proxy artifact, persists unchanged. **Still unverified**.
- **Croogloo features** (`croogloo.com/features/`): re-confirmed 404, no
  change since FR-87's "genuinely gone" conclusion. No new `WebSearch`
  re-run this shift (FR-87 already exhausted that angle on 2026-09-25 and
  found only the same dead URL and help-center articles); the
  call-sheet-specific revision-history UI claim stays **unverified**, per
  this item's own failure case, not guessed from the help-center pages.
- **StudioBinder mobile/offline** (the FAQ article FR-83 named,
  `support.studiobinder.com/en/articles/1065638-is-there-a-mobile-or-tablet-app-available`):
  a genuine change — FR-83 (2026-09-24) found this URL timing out on both
  attempts; today it is reachable (HTTP 200, 73,816 bytes). But the raw
  HTML is a client-rendered Next.js page: the only substring matches are a
  JSON-LD breadcrumb (`"name":"Is there a mobile or tablet app
  available?"`) and an Intercom chat-widget string ("You're not signed in
  on this browser..."), neither of which is the article's actual answer
  text. This is the same class of gap FR-83 found and FR-90 then closed
  for StudioBinder's pricing page (client-rendered, needs a headless
  browser, not a plain fetch) — not closed here, since this item's dod is
  to dispatch and record, not to extend the render script. **Still
  unverified**, cause narrowed from "times out" to "reachable but
  needs a headless render to read the real answer text" — a one-line
  addition to `render_pricing_pages.py`'s target list (the FR-90 pattern,
  not attempted this shift to keep this item's scope to its own dod) is
  the concrete next step, not a repeat dispatch of the same unmodified
  workflow.

No claim in this pass flipped from unverified to confirmed; none needed a
correction (the discipline FR-89 used for the Movie Magic price). Every
one of the four is recorded above with its own current reason, not
retried silently or guessed from memory, per this item's failure case.

## H4 recheck: does any incumbent offer script-to-schedule AI drafting? (FR-150, 2026-10-08)

BRIEF.md's H4 (2026-09-18) names FilmRunner's differentiation claim as
AI-assisted generation of a call sheet from a pasted script in minutes,
asserting "nobody can demo this today — not Movie Magic, not StudioBinder,
not Yamdu" — and flagged that this specific claim had never been checked
against this doc's own teardown. This pass checks all five incumbents named
above for an AI script-breakdown or AI script-to-schedule feature, using
each vendor's own pages (`WebSearch` snippets quoting the vendor directly,
upgraded to a primary-source headless render for Yamdu's two AI pages via
`scripts/render_pricing_pages.py` + `desk-research-reverify.yml`, dispatched
from a throwaway branch not merged to `main`, same pattern as FR-90/108/115/149
— [run 37762341912](https://github.com/sandovabarbora/filmrunner/actions/runs/37762341912)).

- **Yamdu — confirmed present, for script-to-breakdown (not script-to-schedule).**
  This is a real, direct contradiction of H4's own wording. Yamdu's own
  rendered page ([yamdu.com/en/lp/script-breakdown/](https://yamdu.com/en/lp/script-breakdown/),
  rendered 2026-10-08) states plainly: "Import scripts from Final Draft,
  Fountain, Celtx, or even PDF. Let Yamdu scan and arrange all the scene
  information to help get you started right away," and under
  "AI-Enhanced Script Tagging": "Tag the script or let Yamdu's AI create
  breakdown suggestions for the creative departments to confirm and add
  costumes, props, and other elements to your breakdown." It also auto-detects
  characters and locations from the script import. Yamdu's own AI-info page
  ([yamdu.com/en/ai-info/](https://yamdu.com/en/ai-info/), rendered 2026-10-08)
  dates this feature's launch: "Start of the AI features beta test, including
  breakdowns (2025-10-28)" — a beta that started just over eleven months
  before this check; the page does not say whether it has since left beta.
  **The schedule step itself stays manual, even for Yamdu**: the same
  script-breakdown page's "Quick, Dynamic Planning" section describes moving
  from breakdown to shooting schedule by dragging and dropping scenes on a
  stripboard, with breakdown data "auto-filled" into it — no AI claim for
  schedule generation itself, only for the breakdown step that feeds it.
  So H4's narrower claim ("nobody offers AI-assisted script breakdown")
  is false for Yamdu specifically; H4's broader claim (full script-to-schedule
  generation with no human in the loop) still holds for Yamdu, since
  scheduling remains a manual stripboard action.
- **StudioBinder — confirmed absent.** StudioBinder's own script-breakdown
  page ([studiobinder.com/script-breakdown-software/](https://www.studiobinder.com/script-breakdown-software/),
  `WebSearch`-quoted directly 2026-10-08) describes manual element tagging
  that feeds the schedule and call sheet; the only named automation is that
  "when characters have dialogue in a scene, the software automatically
  assigns cast IDs" — not AI-driven tagging or scheduling. StudioBinder's own
  2026 blog post "16 Best AI Filmmaking Tools" treats AI as an external
  category (suggesting a user run ChatGPT over their own script), not a
  StudioBinder-built feature, and never claims the product itself runs AI
  tagging or scheduling. A third-party comparison table (Filmustage, archived,
  checked 2026-10-08) independently marks StudioBinder's "Automatic Script
  Breakdown" as absent. Confirmed absent from the vendor's own page.
- **SetHero — confirmed absent, in the vendor's own words.** SetHero's FAQ,
  rendered directly this shift (not a `WebSearch` snippet — the full page
  text came back clean this time, unlike FR-83/90/135's earlier 403/202
  blocks on this same domain): "Does SetHero do scheduling or script
  breakdowns? Currently, SetHero does not do scheduling or script
  breakdowns. An awesome tool we recommend using for that is
  https://thinkcrew.com/" ([sethero.com/faq/](https://sethero.com/faq/),
  rendered 2026-10-08). The most direct, most confirmed answer of the five —
  SetHero explicitly disclaims both scheduling and breakdown, AI or
  otherwise, and points customers elsewhere.
- **Croogloo — still unverified, same root cause as this doc's other
  Croogloo gaps.** `croogloo.com/features/` — the page most likely to state
  an AI claim if one exists — is confirmed 404 (FR-87, re-confirmed FR-135);
  no replacement marketing page was found by a fresh `WebSearch` this shift
  either. The reachable support docs describe a "Parse Script" option
  ([support.croogloo.com Scripts & Sides](https://support.croogloo.com/en/collections/2618123-scripts-sides),
  checked 2026-10-08) with no AI language anywhere in the visible help-center
  titles or excerpts. This is suggestive of "absent" but not a confirmed
  claim from a vendor marketing page the way StudioBinder/SetHero/Movie
  Magic are — stays **unverified**, per this item's own failure case, same
  as the revision-history-UI gap above.
- **Movie Magic Scheduling — confirmed absent.** The official manual
  (`mms-docs.ep.com`, `WebSearch`-quoted directly 2026-10-08) describes
  script import as literal element-name matching: a plain `.fdx` import
  brings in only the slugline and speaking characters, and a tagged `.sex`
  ("Scheduling Export") file carries element data that is matched against
  existing elements by name, creating new ones automatically on a mismatch —
  rule-based import, not content understanding. EP's release notes (checked
  back to the 10.4.22 beta, November 2023) and support FAQ never use AI/ML
  language for this feature. Confirmed absent from the vendor's own
  documentation, the deepest primary-source confirmation of the five since
  it comes from the product manual itself, not a marketing page.

**Net effect on H4**: the broad claim ("full script-to-schedule AI
generation, no incumbent offers it") still holds across all five — nobody
generates a *schedule* from a script via AI, FilmRunner's wedge is intact
on that front. But H4's own wording names "not Yamdu" specifically for the
general AI-assisted claim, and Yamdu's AI-assisted *script breakdown*
(the step immediately before scheduling) is real, in beta since
2025-10-28, confirmed from Yamdu's own pages — so H4 as literally worded
is now **confirmed false for that one claim** and needs a narrower formulation
(AI-assisted *scheduling* specifically, not breakdown) if it is to keep
being used in positioning copy.
## Headless-render pass (FR-138, 2026-10-06)

FR-135's own next step above — add the StudioBinder mobile/offline FAQ
URL to `render_pricing_pages.py`'s target list and re-dispatch — done
this shift. `scripts/render_pricing_pages.py` gained a
`studiobinder-offline-faq` target; `.github/workflows/desk-research-reverify.yml`
itself was not touched. Dispatched on branch
`docs/fr-138-studiobinder-offline-faq` ([run 37469123815](https://github.com/sandovabarbora/filmrunner/actions/runs/37469123815)),
job log read directly: the page is reachable (HTTP 200, 34 rendered text
lines) and this time exposes its real answer text, not just the JSON-LD
breadcrumb and Intercom string FR-135 found. See the corrected "View
offline" bullet above for the resolution and its own caveat: the article
confirms no native iOS/Android app exists (mobile access is a
mobile-responsive web view), which is evidence consistent with "not
offline-capable today," but the article never uses the word "offline"
and does not itself confirm or deny the original "in the pipeline"
roadmap claim — recorded as a partial resolution, not guessed past what
the page actually says, per this item's own failure case.

## SetHero no longer bot-walled, still no matching figure (FR-149, 2026-10-08)

FR-149 was proposed (2026-10-08 morning brief) to headless-render Yamdu
pricing and SetHero pricing/FAQ, and separately to resolve StudioBinder's
mobile/offline claim — but both were mistaken premises, caught before any
doc was wrongly rewritten: Yamdu/SetHero were already rendered twice (FR-90,
re-confirmed by FR-135) with nothing new to find, and StudioBinder's
mobile/offline claim is the section directly above, already resolved by
FR-138 two days earlier (PR #378, merged after this item was proposed and
started — a genuine duplicate caught only once this PR's conflict with
`main` surfaced it, not before; see `BACKLOG.md`'s FR-149 note for the
correction and the process gap it names). Re-running the dispatch
([run 37748564705](https://github.com/sandovabarbora/filmrunner/actions/runs/37748564705))
did surface one small, non-duplicate fact worth keeping: SetHero's
`/pricing/` and `/faq/` pages no longer return the FR-83/90 202
holding/interstitial response — both now return their real pages (200,
57 and 122 rendered lines respectively) — but neither page states a
figure matching this doc's "$19/month" claim, so that claim stays
**unverified**, cause narrowed from "bot-walled" to "reachable, no
matching figure on the page" rather than confirmed.

## Wayback Machine checked for Yamdu/SetHero pricing (FR-158, 2026-10-12)

FR-158 was proposed (2026-10-12 morning brief) because four separate live-
page attempts (FR-83, FR-90, FR-148, FR-149) had all found Yamdu's and
SetHero's pricing pages fully loading but carrying zero pricing text — the
figure is injected client-side after load. `web.archive.org` is a
genuinely different source, never tried before: an older crawl might
predate whatever hides the figure today, or might have been captured after
the page's own JS had run. New `scripts/fetch_wayback_pricing.py` queries
the Internet Archive's CDX API for each URL, fetches the most recent `200`
snapshot's raw content (the `id_` modifier, which suppresses Wayback's own
toolbar/link-rewriting), and dumps the same stripped-text view
`fetch_page_text.py` uses. Dispatched from throwaway branch
`marketing/fr-158-wayback-pricing-throwaway` (not merged, same unmerged-
branch precedent as FR-108/115/154/155/156) via the existing open-egress
`desk-research-reverify.yml` pattern, twice — the second run after raising
the per-request timeout from 20s to 45s and adding up to 3 CDX retries,
once the first run's single CDX attempt for SetHero timed out with no
result either way
([run 1](https://github.com/sandovabarbora/filmrunner/actions/runs/38216641044),
[run 2](https://github.com/sandovabarbora/filmrunner/actions/runs/38216952240)).
Both runs read directly from the job log, not a `WebSearch` snippet.

- **Yamdu — checked, genuinely exhausted, same gap as the live page.**
  Both runs found the same most-recent `200` snapshot,
  `20260513131415` (2026-05-13), fetched cleanly (200, 19,574 bytes) and
  stripped to only 20 text lines — nav/menu/footer items and a copyright
  line, the identical "page loads, no pricing text" shape FR-90/FR-135
  already found on the live page. The archived crawl was evidently taken
  after the page's chrome rendered but before (or without) whatever
  client-side call injects the actual price, so an older snapshot does not
  help here. The "$45/month Flex, $265/month Core" claim stays
  **unverified, Wayback Machine checked and exhausted** per this item's
  own failure case — no further retry of the live page or this same
  archive query is useful.
- **SetHero — not completed, a different failure mode from "checked and
  exhausted."** The CDX lookup for `sethero.com/pricing/` timed out on
  every attempt across both runs (1 attempt at 20s, then 3 attempts at 45s
  each) — `web.archive.org`'s own CDX search endpoint, not the snapshot
  fetch itself, never returned a response from this open-egress runner.
  This is stated plainly as **unverified, Wayback Machine lookup could not
  be completed (CDX API consistently times out from this egress pattern)**
  — distinct from Yamdu's result above, since no snapshot list was ever
  obtained either way, not a negative result. The "$19/month" claim is
  unchanged from FR-149's own wording. A future attempt could try the CDX
  API's `.txt` output (plain, not JSON) or a direct `/web/timemap/link/`
  request instead of `/cdx/search/cdx`, but that is a genuinely different
  query shape, not a third retry of the same one.

## Follow-up needed (cannot be done by this routine)

- Re-run this teardown with working `WebFetch`/browser access to read
  each vendor's pricing and product pages directly, and resolve every
  item still marked **unverified** above (Yamdu pricing — now also
  checked against its own Wayback Machine history, genuinely exhausted;
  SetHero pricing/FAQ — now reachable but still no matching figure, and
  its Wayback Machine CDX lookup could not be completed rather than
  checked-and-exhausted, see FR-158 above — StudioBinder mobile/offline is
  resolved as far as a rendered page can take it, per FR-138 above; only a
  vendor statement using the word "offline" itself would close the
  remaining gap). Croogloo revision-history UI is no
  longer an open next step for this routine: FR-148 (2026-10-08) rendered
  the three help-center articles FR-136 found adjacent to the question and
  FR-151 (2026-10-08, same day) followed up with five further differently
  worded `WebSearch` queries plus a direct browse of the help center's
  own collections/search index — none of it addresses the question, and
  this pass exhausted the search avenues this routine's tools can reach
  (direct `WebFetch` to `support.croogloo.com`/`croogloo.com` stays
  egress-blocked). The claim stays **unverified, exhausted** until
  someone with a Croogloo account can check the in-app UI directly, or a
  future search surfaces a vendor statement this pass's queries missed —
  not something a further re-search with `WebSearch` alone is likely to
  resolve.
- Confirm current-year (2026) pricing directly on each vendor site —
  several figures above come from third-party aggregators that may lag
  the vendor's own page.
- A fresh `WebSearch` for Croogloo's current features URL, if a future
  pass wants to re-check whether FR-87's "genuinely gone" conclusion
  (2026-09-25, re-confirmed by FR-135 above on 2026-10-06) still holds.
  The Movie Magic pricing discrepancy is resolved (FR-89), and the
  StudioBinder/SetHero-export client-rendering gap is resolved (FR-90),
  both above.

# Prague market sizing: how many active productions are there

FR-20. Role: pm/marketing. Date checked: 2026-09-21. Serves BRIEF.md Q5
(is Prague dense enough for word-of-mouth distribution, or is the first
market elsewhere).

## Definition

"Active production" = one that issued a call sheet in the last 30 days
(BRIEF.md Q5's own definition). No public source counts this directly —
nobody publishes a rolling 30-day call-sheet-issuance count for any city.
What follows are proxies for order of magnitude, each dated and sourced,
not a substitute for that number.

## Method and the same limitation prior desk-research items hit

`WebFetch` was tried against six domains this shift (Czech Film
Commission's own statistics page, `filmcenter.gov.cz`'s 2024 review page,
`productionlist.com`'s Prague listing, and `en.wikipedia.org`) and
rejected by this session's egress proxy every time — the same block
FR-2/FR-21/FR-22 documented for vendor and Czech industry domains, now
also confirmed against Wikipedia itself, which no prior shift had tried.
Everything below is built from `WebSearch` result snippets. Anything a
snippet did not cover is marked **unverified**, not guessed, per this
item's own failure case.

## Proxy counts found

- **Czech films released, 2025**: 88 Czech films and co-productions
  premiered in Czech cinemas in 2025 — 49 fiction, 36 documentary, 3
  animated (Czech Film Center, "Český film v roce 2025",
  `filmcenter.gov.cz/cs/novinky/cesky-film-v-roce-2025`, checked
  2026-09-21, via `WebSearch` snippet). This measures completed films that
  reached distribution in 2025, most of which were shot in 2024 or
  earlier — a proxy for annual completed-production *volume*, not for how
  many productions are actively shooting (and issuing call sheets) in any
  given 30-day window.
- **Incentive applications, 2025**: production companies applied for
  Czech incentives totalling $447 million in 2025, a 140% increase on
  2024 (Screendaily, "Czech Republic sees impact of revamped audiovisual
  fund and new studio facilities", `screendaily.com`, checked 2026-09-21,
  via `WebSearch` snippet). Signals strong recent growth in production
  spend; not a production count, and incentive-scale figures skew toward
  larger, often foreign productions (the incentive minimum spend excludes
  the smallest shoots).
- **Named large productions active in the 2025–2026 window**: Skydance's
  *Ride Or Die*, Netflix's *The Age of Innocence* (Prague and Liberec,
  October 2025–February 2026), Apple TV's *Foundation* season 4 at Prague
  Studios, and the miniseries *Dešťová hůl* (South Bohemia, from February
  2026) all surfaced by name (Screendaily and Cineuropa coverage, checked
  2026-09-21, via `WebSearch` snippets). These are individually confirmed,
  large, foreign-facing productions — useful as existence proof that
  multiple sizeable productions overlap in time in the Prague region, but
  not a count of the whole market, which also includes Czech-only
  productions, series, ads, and student work these outlets do not track.
- **productionlist.com Prague listing**: a `WebSearch` snippet on this
  directory's own Prague page states 20 film and TV productions in its
  database have filmed or are filming in Prague
  (`productionlist.com/production-location/prague-czech-republic`,
  checked 2026-09-21). The page itself could not be read directly
  (`WebFetch` blocked), so the exact date range behind that count is
  **unverified** — it reads as an all-time or multi-year total for that
  database, not a 30-day window, and the database itself likely skews
  toward internationally-facing productions a location-scouting service
  would track, undercounting Czech-domestic, indie, and student
  productions.
- **FAMU student output**: FAMU has produced more than 15,000 student
  films across roughly seven to eight decades of the school's existence
  (multiple `WebSearch` snippets citing FAMU's own anniversary materials,
  checked 2026-09-21); no per-year breakdown was found. FAMU allocates
  CZK 8.4 million per production year to cover external costs for
  students making films in its accredited programmes (`WebSearch`
  snippet citing FAMU's own materials, checked 2026-09-21) — confirms
  meaningful, ongoing annual student production activity, but gives no
  headcount of productions or shoot days.
- **Czech Film Commission's own statistics page**
  (`filmcommission.cz/en/statistics/`) exists and is titled exactly for
  this purpose, but could not be read this shift (`WebFetch` blocked) and
  no `WebSearch` snippet surfaced its actual numbers. This is the single
  most likely authoritative source for a real count and is flagged as a
  follow-up for whoever next has working `WebFetch` or can browse
  directly.
- **Prague Film Office / Magistrát permit counts**: no public source
  states how many filming permits the Magistrát issues per year. Every
  search surfaced process/guide pages (how to apply, lead times), never a
  volume figure. **Unverified** — marked explicitly rather than guessed,
  per this item's failure case.

## Order-of-magnitude estimate (explicitly not a precise count)

No single source gives the 30-day active-production count BRIEF.md Q5
asks for. Combining the proxies above — roughly 88 Czech films completing
per year (so a comparable order rolling through production at any time),
several large foreign productions confirmed overlapping in the current
window, an unquantified but real annual FAMU/other-film-school output,
and an unknown volume of ads, corporate video, and shorts that also use
call sheets but appear in none of these sources — a Prague-region count
of "active productions in the last 30 days" plausibly sits in the low
tens to low hundreds once every production size is included, with large
uncertainty on the top end because the smallest and most numerous
category (student, ad, and micro-budget shoots) is exactly the category
none of these sources track. This is a reasoned estimate built by
combining several partial proxies, not a fact from any one of them, and
should be labelled as such wherever it is cited.

## Comparison against a word-of-mouth sample-size threshold

Diffusion-of-innovations research (Everett Rogers) is commonly summarised
as: an innovation adopted by roughly 15–20% of an audience reaches
critical mass and spreads on its own via word of mouth, without needing
further push ("Reading: Diffusion of Innovation", *Principles of
Marketing*, Lumen Learning OER,
`courses.lumenlearning.com/clinton-marketing/chapter/reading-diffusion-of-innovation/`,
checked 2026-09-21, via `WebSearch` snippet, itself citing Rogers'
*Diffusion of Innovations*). This is a paraphrase from a marketing
textbook, not Rogers' primary text or Wikipedia's summary of it — both
were unreachable this shift (`WebFetch` blocked for `en.wikipedia.org`
too) — so treat the exact 15–20% figure as a widely-repeated
approximation, not a precisely sourced number, and re-verify against
Rogers' own text when egress allows.

Applying it: the relevant "audience" for word-of-mouth spread is not the
general public but the people who actually assemble call sheets (BRIEF.md
Q1's own target: 1st ADs, 2nd ADs, production coordinators) — one to a
few per active production. If the order-of-magnitude estimate above (low
tens to low hundreds of active Prague productions) holds, the addressable
audience of call-sheet-assemblers is itself only on the order of dozens
to a few hundred people at any time. A 15–20% critical mass of that
audience is a small absolute number — plausibly single digits to a few
dozen people — which is compatible with FR-3's plan (five interviews,
sourced first from the founder's network, then FAMU and other fallback
channels) as a realistic path to meaningful word-of-mouth density,
*if* the order-of-magnitude estimate above is roughly right. It does not
confirm Prague is dense enough; it shows the threshold is not obviously
out of reach for a market this size, which is a weaker claim.

## Failure case: no public source establishes the count

Per this item's own failure case, no public source could establish the
30-day active-production count Q5 asks for, so none is asserted as fact.
The narrowest fallback proposed: FR-3's interviews (still blocked on
INBOX #1) should add one estimation question — "how many other
productions of your size do you think were shooting in the Prague region
in the last month?" — cross-checked against the interviewee's own
production-size band (short/feature/feature-TV, the same coding FR-3's
script already uses). That is a direct estimate from people who would
know, rather than further desk research against sources that do not
publish the figure. Until FR-3 runs, this document's order-of-magnitude
estimate is the best available substitute and should be labelled as an
estimate, not a count, wherever cited (e.g. in FR-25's landing page copy
or any future pitch materials).

## Re-verification pass (FR-83, 2026-09-24)

`scripts/reverify_desk_research.py`, run as a GitHub Actions job with open
egress (`.github/workflows/desk-research-reverify.yml`), fetched the pages
this doc names as blocked:

- **Czech Film Commission statistics page** (`filmcommission.cz/en/statistics/`):
  reachable (200, 126 KB) for the first time — this shift's own attempt, and
  every prior one, hit the sandbox proxy instead. The page title, `Statistics
  | Czech Film Commission`, confirms it is the right page. The re-verify
  script's own substring checks only matched navigation text and the title,
  not a specific production-count figure in the body — so this closes the
  "can we even reach it" half of the gap, not the "what does it say" half.
  **Still the top follow-up**: read the page body directly (not via a
  keyword-substring script) for the actual count.
- **productionlist.com Prague listing**
  (`productionlist.com/production-location/prague-czech-republic`): now
  **404**, not merely blocked. The URL this doc cites (2026-09-21) may have
  moved since, or the search snippet it was built from was already stale.
  Flag as a stale citation — a fresh `WebSearch` for productionlist.com's
  current URL structure is needed before this count can be re-checked,
  rather than treating the 404 as the listing having been removed.
- **Diffusion of Innovations** (`en.wikipedia.org/wiki/Diffusion_of_innovations`):
  reachable (200) — Wikipedia was blocked from this sandbox on every prior
  attempt, including this doc's own. The article does describe Rogers'
  adopter-category framework and the "critical mass" concept the
  Lumen-Learning paraphrase this doc cites is itself paraphrasing; it names
  the classic breakdown (innovators + early adopters together are commonly
  put at roughly 13.5–16% of an audience, the threshold before the "chasm"
  to the early majority). This is a genuine upgrade in sourcing — Wikipedia's
  own article, not a marketing-textbook's paraphrase of a paraphrase — and
  is now citable directly for the shape of the claim (early adoption
  clusters in the mid-teens percent range), though the exact "15–20%"
  figure this doc uses is still not verbatim in the source; a careful reader
  should treat the two as compatible, not identical, until someone reads
  Rogers' primary text.

Full raw output (status, byte length, every substring match with its
excerpt) is in the job's own log and artifact.

## Re-source attempt for the productionlist.com stale citation (FR-87, 2026-09-25)

FR-83 flagged `productionlist.com/production-location/prague-czech-republic`
as newly 404 and asked for "a fresh `WebSearch` for productionlist.com's
current URL structure… before this count can be re-checked." That search
was run this shift several ways (a direct query, a `site:productionlist.com
Prague` query, and a query for other cities' listing pages to learn the
site's current URL pattern) — every one returns the exact same dead URL as
a top result ("Film & TV Productions Filming in Prague, Czech Republic |
Production List"), and the site clearly is live: `site:productionlist.com`
results show working production pages (e.g. `/production/blade-runner-2099`,
`/production/interview-vampire-season-3`) and a working sibling listing at
`/production-location/los-angeles-ca`, confirming the `/production-location/
<slug>` pattern is still current for other cities. To rule out the
non-www/www split before concluding the page is actually gone, the re-verify
job (`scripts/reverify_desk_research.py` via
`.github/workflows/desk-research-reverify.yml`, open egress) was re-run
today against the bare host and, on a throwaway branch (not merged),
temporarily extended to also probe `https://www.productionlist.com/
production-location/prague-czech-republic`. Both came back **404** from the
open-egress runner (run [36111762139](https://github.com/sandovabarbora/filmrunner/actions/runs/36111762139)
for the bare host, [36111869883](https://github.com/sandovabarbora/filmrunner/actions/runs/36111869883)
for the www probe).

**Conclusion: genuinely gone, not a fetch/proxy artifact or a www/non-www
mismatch** — the Prague-specific slug 404s on both hosts while the same
`/production-location/<slug>` pattern works for other cities, so this reads
as Prague's listing being removed or renamed to a slug this shift could not
guess (`prague-czechia`, `prague-cz` and the plain `prague-czech-republic`
already tried all point nowhere), not as the URL scheme having changed
sitewide. As with the Croogloo citation above, the search index still
serves the dead URL's cached title as if it resolves — flagged so a future
pass fetches before trusting a `WebSearch` snippet on this exact URL. No
live replacement was found; the "20 productions" figure stays **unverified**
and the order-of-magnitude estimate in this doc is unchanged (it never
depended on this single proxy count alone). Checked 2026-09-25.

## Follow-up needed (cannot be done by this routine)

- Read `filmcommission.cz/en/statistics/`'s body directly (now confirmed
  reachable, 2026-09-24) for the actual production-count figures — the
  single most likely source for a real, citable count.
- Find productionlist.com's current Prague-listing URL via a fresh
  `WebSearch` (the 2026-09-21 citation now 404s) and read it directly.
- Re-verify the 15–20% critical-mass figure against Rogers' own text — the
  Wikipedia article is now reachable (2026-09-24) and names a compatible
  but not identical range; Rogers' primary text is the next step.
- Once FR-3 interviews happen, fold interviewees' own estimates into this
  file rather than treating this shift's order-of-magnitude figure as
  final.

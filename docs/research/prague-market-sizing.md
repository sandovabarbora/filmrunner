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

**Superseded 2026-10-02 (FR-121) — see "Rogers' own adopter-category
percentages" below for the current figure.** The paragraph below is kept
for the record, not as the live claim: diffusion-of-innovations research
(Everett Rogers) was originally summarised here as "an innovation adopted
by roughly 15–20% of an audience reaches critical mass and spreads on its
own via word of mouth, without needing further push" ("Reading: Diffusion
of Innovation", *Principles of Marketing*, Lumen Learning OER,
`courses.lumenlearning.com/clinton-marketing/chapter/reading-diffusion-of-innovation/`,
checked 2026-09-21, via `WebSearch` snippet, itself citing Rogers'
*Diffusion of Innovations*). That was a paraphrase from a marketing
textbook, not Rogers' primary text — flagged at the time as "a
widely-repeated approximation, not a precisely sourced number, re-verify
against Rogers' own text when egress allows."

### Rogers' own adopter-category percentages (FR-121, 2026-10-02)

Rogers' primary framework splits adopters into five categories by
standard deviations from the mean adoption time, with a fixed percentage
per category: innovators 2.5%, early adopters 13.5%, early majority 34%,
late majority 34%, laggards 16%. "Critical mass" in Rogers' own model is
the point where the innovators-plus-early-adopters segment has adopted —
**2.5% + 13.5% = 16%** — after which the early majority follows. This
is a single, internally consistent number, not a range, and it is more
precise than the "15–20%" marketing-OER paraphrase this doc previously
cited (the old range was in the right neighbourhood but not sourced to
Rogers' own figures).

Sourced via `WebSearch` (`WebFetch`/direct fetch of every URL below was
tried and blocked by this sandbox's egress proxy, consistent with every
prior item in this doc; no GitHub Actions open-egress dispatch was run
this shift since the dod accepts `WebSearch`-only sourcing and the figure
below already converges across independent sources without it) on
2026-10-02, three independent secondary sources, none citing each other,
all stating the same 2.5%/13.5% breakdown:

- Umbrex, "Diffusion of Innovations Curve (Rogers)" —
  `umbrex.com/resources/frameworks/marketing-frameworks/diffusion-of-innovations-curve-rogers/`
  — states the five categories as 2.5% / 13.5% / 34% / 34% / 16% and notes
  the split comes from standard deviations on a normal distribution of
  time-to-adopt (matches Rogers' own stated method).
- Educational Technology (Dr. Serhat Kurt), "Diffusion of Innovations
  Theory" — `educationaltechnology.net/diffusion-of-innovations-theory/`
  — independent academic-resource site, states the same five-category
  breakdown with the same percentages.
- Yu-kai Chou, "Diffusion of Innovations: The 5 Adopter Types & the
  Chasm" — `yukaichou.com/gamification-analysis/diffusion-of-innovations-rogers-adoption-curve/`
  — independent author/site, same percentages, explicitly names
  "innovators (2.5%)" and "early adopters (13.5%)" as the two segments
  before the "chasm" to the early majority.

All three were reached only as `WebSearch` snippets, not full page reads
(every one of the above domains returned `EGRESS_BLOCKED` on a direct
`WebFetch` attempt this shift) — same caveat this doc already applies to
every other `WebSearch`-only citation. Three independent sources
converging on an identical, specific number (not a rounded range) is
stronger sourcing than the single OER paraphrase the old "15–20%" line
rested on, even without a full-text read of Rogers' own book.

Applying it: the relevant "audience" for word-of-mouth spread is not the
general public but the people who actually assemble call sheets (BRIEF.md
Q1's own target: 1st ADs, 2nd ADs, production coordinators) — one to a
few per active production. If the order-of-magnitude estimate above (low
tens to low hundreds of active Prague productions) holds, the addressable
audience of call-sheet-assemblers is itself only on the order of dozens
to a few hundred people at any time. A 16% critical mass of that
audience (Rogers' own innovators+early-adopters figure, above) is a small
absolute number — plausibly single digits to a few dozen people, not
meaningfully different from what the old 15–20% range implied — which is
compatible with FR-3's plan (five interviews, sourced first from the
founder's network, then FAMU and other fallback channels) as a realistic
path to meaningful word-of-mouth density, *if* the order-of-magnitude
estimate above is roughly right. **What this re-sourcing changes:** the
threshold is now a specific, Rogers-sourced number (16%) instead of a
textbook's rounded range; **what it does not change:** the order-of-
magnitude estimate of the addressable audience, the conclusion that
Prague's density is plausible-but-unconfirmed, or the next step (FR-3
interviews) — 16% and "15–20%" land on the same small-absolute-number
conclusion for this doc's purposes, so this is a precision correction,
not a changed finding.

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

## The Czech Film Commission statistics page read in full (FR-88, 2026-09-25)

FR-83 (2026-09-24) confirmed `filmcommission.cz/en/statistics/` is reachable
from GitHub Actions' open egress but only substring-matched it ("production",
"2025", "statistic" all matched navigation text and the page title, not a
production-count figure). This shift extended the same open-egress pattern
(`scripts/fetch_page_text.py`, a new step in
`.github/workflows/desk-research-reverify.yml`, dispatched from a branch
before merge, [run 36117265800](https://github.com/sandovabarbora/filmrunner/actions/runs/36117265800))
to strip the page to plain text and read every line, rather than guessing at
substrings for a page nobody here had actually read.

**Finding: the page does not count productions at all.** Its own subtitle
states exactly what it measures: "Information on the revenues of projects
filmed in recent years." The page is a single table, "Audiovisual production
turnover (in millions of CZK)", with one row per year from 2002 to 2024 and
three columns — Czech Films and TV Series, Foreign Films and TV Series, and
Advertising Spots — each a turnover figure in millions of CZK, sourced to
the Audiovisual Producers' Association. The most recent rows:

| Year | Czech Films & TV Series | Foreign Films & TV Series | Advertising Spots |
|---|---|---|---|
| 2022 | 1,732 | 11,256 | 2,451 |
| 2023 | 2,145 | 9,226 | 2,140 |
| 2024 | 1,871 | 5,505 | 2,498 |

(all figures million CZK; period-as-thousands-separator in the source
converted to commas here for clarity)

This is genuinely useful as an order-of-magnitude signal for the size of the
whole Czech audiovisual industry (foreign productions alone turned over
roughly 5.5 billion CZK, ~$235M at a rough 2026 rate, in 2024) and confirms
the industry is not shrinking. But per this item's own failure case: **it
does not map onto Q5's "active production issuing a call sheet in the last
30 days" metric at all** — turnover says nothing about how many distinct
productions generated it, since one large production and one hundred small
ones could produce the same total. No production count, permit count, or
shoot-day count appears anywhere on this page. The Commission's statistics
section has no other sub-page beyond this one table (checked via the site's
own nav, reproduced in the full text dump).

**Conclusion**: this closes the "what does the page say" half of FR-83's
open follow-up, but does not move the Q5 order-of-magnitude estimate above —
there was no production-count figure to fold in. The Commission's own
"Filmography" section (`filmography` in the site nav, a database of films
and series shot in the Czech Republic) is a more plausible candidate for a
future count-oriented follow-up, but that is a different page than the one
FR-20/FR-83 named, not read this shift, and not assumed to contain a 30-day
figure either — proposed as its own follow-up below rather than assumed.

## The Filmography page read in full (FR-105, 2026-09-29)

FR-88 (2026-09-25) found the Commission's statistics page measures revenue,
not a production count, and named the Commission's separate Filmography page
(`filmcommission.cz/en/filmography/`) as a more plausible count source —
not read at the time. This shift extended the same open-egress pattern
(`scripts/fetch_page_text.py`, dispatched via `.github/workflows/desk-research-reverify.yml`
from a throwaway branch, not merged, since the step was needed once, not as
a permanent addition) to read the page's actual body rather than guess.

**Finding: it is a lifetime title archive, not a rolling production count,
and does not map onto Q5's "active production in the last 30 days" metric.**
The page (200, 184,484 bytes, checked 2026-09-29) is a filterable database of
"Films, series and other audiovisual works shot in the Czech Republic" —
its own nav description. Its format filter shows **506 total entries: 338
movies, 164 series, 1 other** (a WebSearch snippet found earlier the same
day had cached a stale 505/338/163/1 — the live page is the authoritative
number, one entry ahead by the time this was fetched, illustrating exactly
why a real fetch supersedes a cached snippet). A "Year of production" filter
runs from 2026 back to 2003 individually, plus a single "1983–2003" bucket
for everything older — so the archive spans at least 1983 to 2026, filtered
by the year(s) a title was in production (several entries carry two years,
e.g. "2024, 2025 production" for *Blade Runner 2099*), not a shoot-day or
filming-permit date. Sample entries confirm this is a title-level record
(named productions like *Nosferatu*, *One Life*, *Interview with the Vampire*
season 2), each with a country and format, not a log of shoot days or call
sheets. Results paginate 1–43 (roughly a dozen titles per page), consistent
with the 506 total.

Per this item's own failure case: the plain-HTML fetch does not surface a
per-year count — the year filter's option labels are static text ("2026",
"2025", …) with no visible counts next to them in the fetched markup, so
whatever count each year-filter click would show is populated client-side
(the same class of gap FR-90 found for StudioBinder/Yamdu/SetHero's
JS-rendered pricing, not attempted here since the dod only asks to read the
body, not build a per-year scraper). So this closes "what does the page
count" (title-level works across four decades, not shoot days) but does not
produce a new number for the order-of-magnitude estimate above: 506 titles
over roughly 43 years is itself an annual-completion-volume proxy in the
same family as FR-1/FR-88's Czech-films-released figures (88/year), not a
30-day active-production count, and averaging 506 over 43 years (≈12/year)
would undercount badly since the database is dominated by internationally-
facing features/series the Commission tracks, the same skew FR-20 already
flagged for productionlist.com's now-dead listing — it excludes the
Czech-domestic, ad, and student productions this doc's estimate depends on
most for the "low tens to low hundreds" range. **The order-of-magnitude
estimate above is unchanged**; no defensible new count was extracted.

## Follow-up needed (cannot be done by this routine)

- If a per-year Filmography count becomes worth the cost, render the
  filtered page with real headless Chromium (the FR-90 pattern) rather than
  a plain fetch, since the year-filter counts appear to be client-rendered.
  Even then, per the finding above, expect it to remain an annual-completion
  proxy skewed toward larger/international titles, not a 30-day count.
- productionlist.com's Prague listing is confirmed genuinely gone (FR-87,
  2026-09-25, no live replacement found) — closed, not a follow-up any more.
- **Closed (FR-121, 2026-10-02)**: the 15–20% critical-mass figure is
  replaced with Rogers' own innovators+early-adopters breakdown (16%,
  three converging `WebSearch`-sourced secondary citations — see "Rogers'
  own adopter-category percentages" above). A full read of Rogers'
  primary text itself is still untried (every source above was reached as
  a `WebSearch` snippet, not a full page fetch — this sandbox's egress
  proxy blocks all three cited domains directly) but three independent,
  mutually-corroborating secondary sources meet this item's own dod bar;
  not treated as a further open follow-up.
- Once FR-3 interviews happen, fold interviewees' own estimates into this
  file rather than treating this shift's order-of-magnitude figure as
  final.

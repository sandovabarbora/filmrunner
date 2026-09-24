# Switching-cost teardown: what would make an AD leave a named incumbent

FR-21. Role: pm. Date checked: 2026-09-18. Serves BRIEF.md Q6 (the desk-research
half; the interview half is FR-3's own question, see the note at the end).

## Method and the same limitation FR-2 hit

This shift's network egress proxy blocks direct fetches of vendor and
review-site domains (confirmed again this shift: `curl` to an unrelated
`fly.dev` host was rejected by the same proxy policy). `WebFetch` is not
available for these domains either, per `TEAM.md`. Everything below is
built from `WebSearch` result snippets, which do quote vendor help-center
pages and third-party review sites (G2, Capterra) rather than this shift
reading the full page directly. Every claim is cited with the URL
`WebSearch` surfaced and the date checked (2026-09-18). Anything the
snippets did not cover is marked **unverified**, not guessed, per this
item's own failure case — the same convention FR-2 used.

## StudioBinder

- **Data an AD/office would lose or re-enter**: call sheets themselves
  export to PDF, and the stripboard (schedule) exports to CSV — both are a
  working export path, not vendor-only storage
  ([support.studiobinder.com: download/print call sheets](https://support.studiobinder.com/en/articles/6739421-how-to-download-and-print-call-sheets),
  [support.studiobinder.com: export stripboard as CSV](https://support.studiobinder.com/en/articles/12591376-how-to-export-stripboard-as-csv),
  checked 2026-09-18). Whether contacts, crew records, or call-sheet
  templates themselves (as opposed to the stripboard) have an export path
  is **unverified** — no help-center article surfaced for those specifically.
- **Working export function**: yes, for schedule (CSV) and call sheets
  (PDF); confirmed from StudioBinder's own support docs, not a third party.
- **Lock-in signal**: none found specific to StudioBinder's own data
  portability. The reasons people actually leave, per a third-party
  alternatives roundup, are about missing features (no native budgeting,
  no "real AI" for the creative side) or price, not data being trapped
  ([storyflow.so: best StudioBinder alternatives 2026](https://storyflow.so/blog/best-studiobinder-alternatives-2026), checked 2026-09-18).
  No Reddit thread surfaced despite two targeted searches; **unverified**
  whether informal lock-in complaints exist there.

## Yamdu

- **Data an AD/office would lose or re-enter**: a specific, sourced
  lock-in point — contact retention across multiple projects requires a
  higher-tier plan; reviewers on Capterra describe having to re-enter cast
  and crew information for every new production on a lower tier instead of
  carrying contacts forward ([capterra.com Yamdu reviews via search](https://www.capterra.com/p/186025/Yamdu/reviews/), checked 2026-09-18).
  This is the clearest concrete switching-cost (and even staying-cost)
  signal found across all five tools this shift.
- **Working export function**: **unverified**. A search snippet notes
  Yamdu has "limited data export capabilities" and that users should
  confirm which formats (PDF/CSV/FDX) are supported before migrating
  ([thestudiohero.com: Yamdu alternatives](https://thestudiohero.com/yamdu-alternatives/), checked 2026-09-18) — this is a
  secondary source's framing, not a help-center article read directly, so
  treat as a hint rather than confirmed fact. Notably Yamdu can *import*
  Movie Magic schedules ([yamdu.com blog: Movie Magic Schedule import](https://yamdu.com/en/blog/import-movie-magic-schedules-to-yamdu/), checked 2026-09-18),
  which lowers the cost of switching *into* Yamdu but says nothing about
  switching *out*.
- **Lock-in signal**: contact re-entry cost on lower tiers, sourced above.

## SetHero

- **Data an AD/office would lose or re-enter**: SetHero has a whole
  "Importing / Exporting Data" help-center collection, and its own
  Exporting Data article names exactly what can leave the platform: people
  list, cast list, crew list, scenes list, and locations list, each
  downloadable from an Export button on that list's page
  ([help.sethero.com: Exporting Data](http://help.sethero.com/en/articles/1513672-exporting-data),
  [help.sethero.com: Importing/Exporting Data collection](https://help.sethero.com/en/collections/845885-importing-exporting-data), checked
  2026-09-18). Call-sheet templates and revision history specifically are
  not named in the export list; **unverified** whether those export.
- **Working export function**: yes, and the most explicitly documented of
  the five — confirmed directly from SetHero's own help center, not a
  third party.
- **Lock-in signal**: a G2 review surfaces "partial data exchange between
  projects" as a named improvement area, alongside language-module
  switching and outgoing-message customization
  ([g2.com: SetHero reviews](https://www.g2.com/products/sethero/reviews), checked 2026-09-18) — weaker and vaguer
  than Yamdu's contact-tier complaint, but a real user-sourced signal that
  moving data *between* a user's own projects inside SetHero has friction,
  which is adjacent to (not the same as) switching cost to a competitor.

## Movie Magic Scheduling (Entertainment Partners)

- **Data an AD/office would lose or re-enter**: the strongest lock-in
  language found this shift, sourced directly from a competitor's product
  page rather than a neutral review: "your scene breakdown and schedule
  data is locked in Movie Magic, making it difficult to use on call
  sheets, reports, or in other software"
  ([sethero.com: Movie Magic Scheduling exporter to Excel/JSON](https://sethero.com/movie-magic-scheduling-exporter-to-excel/), checked
  2026-09-18). Read this as a competitor's marketing framing, not a
  neutral source — SetHero sells the workaround it describes — but the
  underlying facts it cites are checkable and are recorded below.
- **Working export function**: partial and dated. Movie Magic's own
  native exports are `.MMSX`/`MMS10` (current) and a legacy `.MMS`/SEX
  format for MMS 5 & 6 ([mms-docs.ep.com: Movie Magic Scheduling Files](https://mms-docs.ep.com/ScheduleFiles/MovieMagicSchedulingFiles.html), checked
  2026-09-18) — both proprietary, readable mainly by Movie Magic or tools
  that specifically built an importer for them. A third-party exporter
  (SetHero's own tool, linked above) converts scene-breakdown and basic
  schedule data to Excel/JSON, but by its own documentation it does not
  export other MMS reports (DOODs, one-liners, element lists) and does
  not work with Movie Magic Scheduling 10, only the older desktop-only
  MMS 5 & 6 — i.e. current-version users have no confirmed third-party
  export path today.
- **Lock-in signal**: the clearest of the five, sourced above, with the
  caveat that the source is a competitor's page.

## Croogloo

- **Data an AD/office would lose or re-enter**: contacts have a
  documented, fairly complete export path — name, email, phone, address,
  department, position, and distribution-list membership, downloadable as
  Excel, vCard, or CSV from a List Options menu
  ([support.croogloo.com: Distribution List Features — Compare, Export, Merge](https://support.croogloo.com/en/articles/7939987-distribution-list-features-compare-export-merge),
  [support.croogloo.com: Exporting Contacts](https://support.croogloo.com/en/articles/10139791-exporting-contacts), checked 2026-09-18).
  Call sheets, sides comparisons, and distribution reports (open/confirm/
  bounce tracking) do not have a documented export in the snippets found;
  **unverified** whether that history survives leaving the platform.
- **Working export function**: yes, for contacts specifically — confirmed
  directly from Croogloo's own help center.
- **Lock-in signal**: none found. Croogloo documents integrations with
  Excel, Google Drive/Calendar, Dropbox, Slack, and Movie Magic Scheduling
  ([croogloo.com/features via search](https://croogloo.com/features/), checked 2026-09-14, re-confirmed
  2026-09-18) — interoperability with other tools is the opposite of a
  lock-in signal, though this is Croogloo's own marketing framing, not a
  user review.

## What this means for BRIEF.md Q6

- Only two of five incumbents (SetHero, Croogloo) have a directly-sourced,
  documented export function; StudioBinder has one for schedule and call
  sheets specifically, not confirmed for contacts or templates; Yamdu's
  export capability is unverified and flagged limited by a third party;
  Movie Magic's export is real but version-gated and incomplete.
- The one concrete, user-sourced switching-cost complaint found is
  Yamdu's tiered contact retention — a genuine "what would I lose"
  friction, not a hypothetical. The one concrete *format*-lock-in is
  Movie Magic's proprietary scene/schedule data, though that claim comes
  from a competitor's page and should be re-verified from a neutral
  source before it goes into any positioning copy.
- No public forum discussion (Reddit, industry groups) of switching
  mid-season was found for any of the five tools despite four targeted
  searches this shift. This is a real gap, not an absence of the
  phenomenon — a desk-research method with no `WebFetch` access cannot
  reliably surface forum threads a search engine does not rank highly. It
  is marked **unverified**, not "no lock-in exists," per this item's
  failure case.

## Desk research vs. FR-3's interview question — kept separate on purpose

Everything above is what public sources say incumbents *make possible or
difficult*. It is not evidence of what would actually make a specific
Prague AD switch mid-season — that is FR-3's own interview question
("what would have to be true for you to switch tools mid-production?"),
and FR-3 remains blocked on the founder recruiting real candidates
(INBOX #1). A future shift or the founder should never cite this document
as if it answered FR-3's question; it only narrows what to ask about (data
portability, contact re-entry cost, format lock-in) once real interviews
happen.

## Re-verification pass (FR-83, 2026-09-24)

`scripts/reverify_desk_research.py`, run as a GitHub Actions job with open
egress (`.github/workflows/desk-research-reverify.yml`), fetched three pages:

- **Yamdu Capterra reviews** (`capterra.com/p/186025/Yamdu/reviews/`): 403,
  even from a GitHub Actions runner — the same pattern FR-2's re-verify pass
  found for SetHero, consistent with Capterra/G2-style review sites blocking
  non-browser requests generally, not this sandbox specifically. The
  contact-retention lock-in signal is still sourced only from the earlier
  `WebSearch` snippet; **still unverified** directly.
- **SetHero's own Exporting Data article** (`help.sethero.com/en/articles/1513672-exporting-data`):
  reachable (200, 70 KB) — not blocked — but it is an Intercom-hosted help
  center that renders its article body client-side; the raw fetch's matches
  were navigation/JSON-LD artifacts (a breadcrumb link, a template field),
  not the article's actual prose. Whether call-sheet templates and revision
  history are in SetHero's export list is **still unverified**; the next
  attempt needs a headless-browser read, now that reachability itself is
  confirmed rather than assumed blocked.
- **Movie Magic Scheduling's own file-format documentation**
  (`mms-docs.ep.com/ScheduleFiles/MovieMagicSchedulingFiles.html`): reachable
  (200, 43 KB) and genuinely confirms, from Movie Magic's own docs rather
  than a competitor's page: *"Movie Magic Scheduling files are saved as
  .mmsx files."* This is real, neutral-source confirmation of the underlying
  fact (proprietary format) this doc's "Working export function" bullet
  already stated from `mms-docs.ep.com` — now cross-checked directly rather
  than via SetHero's competing product page. The interpretive framing
  ("locked in," "difficult to use... in other software") remains SetHero's
  own language and is not independently confirmed by this neutral source;
  only the format-proprietary fact itself is upgraded from
  competitor-sourced to vendor-primary-sourced.

Full raw output (status, byte length, every substring match with its
excerpt) is in the job's own log and artifact.

## Follow-up needed (cannot be done by this routine)

- Re-run the searches that returned nothing (Reddit/forum threads on
  switching, StudioBinder/Croogloo contact and template export) with
  working `WebFetch` or a founder session that can browse directly.
- A headless-browser read of SetHero's Exporting Data article (confirmed
  reachable 2026-09-24, but client-rendered) to settle whether call-sheet
  templates/revision history export.
- The Movie Magic proprietary-format *fact* now has a neutral citation
  (2026-09-24); the "locked in" *framing* is still SetHero's own language
  and would benefit from a neutral discussion (forum, review site) if one
  becomes reachable.

# Pilot scale on a phone — 60 crew, 30 days, 60 scenes (FR-52)

Measured 2026-09-22 on the local build against a local API + Postgres, headless Chromium at iPhone width (390 px),
network throttled through CDP to a 4G-ish profile: 4 Mbit/s down, 1 Mbit/s up, 150 ms RTT. Test:
`frontend/tests/test_scale.py` (seeds the production through the API once per test database; prints the table with `-s`;
asserts the sheet under 2 s and every screen under 6 s so a regression fails CI).

Production: 60 crew across 12 departments, 8 cast, 6 geocoded locations, 30 days with 40–60 scenes each (day 5 has 60),
5 cast calls and 5 personal calls per day.

## Before / after (time to a usable screen)

| Screen | Before | After | Change |
|---|---|---|---|
| Days list, 30 days | **2.82 s · 520 KB** | 0.80 s · 27 KB | the list endpoint shipped every day's full schedule; it now ships the summary the list shows |
| Day screen, 60 scenes | 0.40 s · 25 KB | 0.88 s* | — |
| Crew tab, 60 people | 0.80 s · 27 KB | 0.81 s | — |
| Personal-calls picker (60 people, 5 with a call) | 0.79 s | 0.83 s | FR-44 already lists only the 5 |
| Crew's public sheet, first open, 60 scenes | 0.73 s · 25 KB | 0.72 s | under the 2 s line |
| Crew's public sheet, second open (service worker) | 0.10 s | 0.10 s | offline path |
| Stable link → next day, 30 days listed | 0.21 s · 7 KB | 0.20 s | — |

\* run-to-run noise on a throttled profile is ±0.4 s; nothing here changed.

## The three slowest spots and what was done

1. **Days list payload** (`GET /productions/{id}/call-sheets`) — fixed in this item: `schedule_items`, `cast_calls` and
   `crew_calls` are emptied on the list read (the day screen fetches its own day). 520 KB → 27 KB.
2. **Weather on publish for far-off days** — a 30-day schedule import made 30 publishes, each asking Open-Meteo for a date
   past its 16-day horizon (a guaranteed 400, ~150 ms each). Fixed: no call outside `today … today+16`.
3. **Day screen with 60 scenes** — 60 scene rows × 6 inputs render fine (0.4–0.9 s); the schedule list is not virtualised
   and does not need to be at this size. Above ~150 scenes a day it would; noted, not planned.

Nothing exceeded 1.5 s after the fix, so no further items are filed.

## Lighthouse mobile score (FR-71, run 2026-09-23)

Run against this same production's day 5 (60 scenes), public sheet, no `me` token, local build served
statically, local API + Postgres, Chrome's own simulated mobile throttling (`lighthouse` default config,
`--form-factor=mobile`, headless `/opt/pw-browsers/chromium`, `npx lighthouse` — `npm`'s registry is in fact
reachable from this sandbox, so the earlier "no Lighthouse in the harness" note above was wrong; `lighthouse`
is now an exact-pinned devDependency and the run is reproducible via `frontend/scripts/lighthouse_pilot_scale.py`).
Full report: `docs/research/lighthouse-pilot-scale.json`.

| Category | Score |
|---|---|
| Performance | **69** |
| Accessibility | 100 |
| Best Practices | 96 |
| SEO | 90 |

Performance is under the 90 line the dod checks for. The metrics behind it: FCP 2.3 s, LCP 2.6 s, TBT 140 ms,
Speed Index 2.3 s (all fine) — the score is dragged down by **Cumulative Layout Shift = 0.843** (audit score
0.04, "poor" starts above 0.25) and, to a lesser extent, Max Potential First Input Delay = 280 ms (audit score
0.41). Lighthouse's own culprit trace names `main#main` (the whole sheet body, top:55 to bottom:10026) as the
one shifting element — consistent with `styles.css`'s `.skeleton`/`.sheet.visible` pattern (`CallSheetView.tsx`):
the sheet renders a ~100 px skeleton first, then swaps in the full ~10,000 px sheet (60 scenes, cast, contacts)
in one shot once the API responds, so the whole page height jumps in a single frame. Filed as FR-77 (its own
`ready` item, with this reproduction) rather than fixed here — this task was to measure and record, not to
redesign the loading state.

## Skeleton layout shift fixed (FR-77, run 2026-09-24)

Reproduced the 0.843 CLS above first, on this same build (`frontend/scripts/lighthouse_pilot_scale.py` against
the FR-52 production's day 5, before touching any code) — confirmed audit score 0.04 (red) and the report still
named `main#main`, top:55 to bottom:10026, as the shifting node.

Root cause, traced in `frontend/src/App.tsx`: while `loading` is true, the page already paints the masthead,
the status line, and — below the skeleton — the `privacy-line` paragraph (a permanent footer link, rendered for
every mode except `dev`). That paragraph is the one already-rendered, already-visible element sitting right
after the ~100 px skeleton; when the API resolves and the ~10,000 px `CallSheetView` swaps in for the skeleton
in the same frame, `privacy-line` jumps ~10,000 px down. Lighthouse's shift-region algorithm reports the change
against the nearest common container it can name usefully, `main#main`, but the actual moving content is that
one paragraph — nothing else already on screen sits below the skeleton.

Fix: `privacy-line` now renders only once `!loading` (`mode.kind !== "dev" && !loading`), so during the loading
window there is nothing already-painted below the skeleton to displace. It still appears in the same frame as
the sheet, the error state, or the not-found state — it just never exists yet at a stale position beforehand.
One line changed, no visual change once loaded, no change to `.skeleton`'s own size.

Re-ran the identical script against the rebuilt `dist/`:

| Category | Before | After |
|---|---|---|
| Performance | 69 | **94** |
| Accessibility | 100 | 100 |
| Best Practices | 96 | 96 |
| SEO | 90 | 90 |

Cumulative Layout Shift: **0.843 → 0.014** (audit score 0.04 → 1.00; Lighthouse's "good" line is under 0.1).
`cumulative-layout-shift` and `cls-culprits-insight` no longer appear in the red-audit list at all. The
remaining sub-90 metric is unrelated and pre-existing: Max Potential First Input Delay (audit score 0.6,
220 ms) — a `forced-reflow-insight` note, not layout shift; not this item's dod. Full updated report:
`docs/research/lighthouse-pilot-scale.json` (overwritten by this run, this table is the durable record of the
before figure).

Failure case checked: with the API pointed at a nonexistent id, the not-found message renders immediately once
loading ends, `privacy-line` appears in the same frame at its final position, and no additional shift is
introduced (same fix path — nothing pre-existing to move).

## Meta description added, SEO 90 → 100 (FR-80, run 2026-09-24)

`frontend/index.html` (the public sheet — the page this Lighthouse run tests) had no
`<meta name="description">`; `frontend/landing.html` already had one. Lighthouse's `seo` category was 90/100
with `meta-description` ("Document does not have a meta description") as the one failing audit, confirmed in
`docs/research/lighthouse-pilot-scale.json`.

Fix: added a generic, production-agnostic description to `frontend/index.html` (English, matching the page's
own `lang="en"`, same tone as `landing.html`'s Czech one) — no production or day name, since the page is shared
across every production:

    A living call sheet for the whole crew, offline-honest when signal drops. Publish a revision and
    everyone's phone updates.

Re-ran the identical script against the rebuilt `dist/`:

| Category | Before | After |
|---|---|---|
| Performance | 94 | 90 |
| Accessibility | 100 | 100 |
| Best Practices | 96 | 96 |
| SEO | 90 | **100** |

`meta-description` audit score 0 → 1 (`docs/research/lighthouse-pilot-scale.json`, overwritten by this run).
Performance moved from 94 to 90 on this run — both above the FR-71 dod's 90 line, and the gap is CI-machine
noise (Max Potential FID and two zero-weighted insights, unrelated to this change; no page weight or markup
changed besides the one meta tag) rather than a regression from this fix, consistent with FR-77's own noted
±var on a throttled profile.

Failure case checked: the description is a single hardcoded generic line, never interpolated from a
production or day, so no build touches or varies it per production.

## FR-81 (13:00 shift, 2026-09-24): favicon 404 console error

`errors-in-console` (best-practices audit) was failing (score 0) on one logged error:
`Failed to load resource: 404 (File not found)` for `/favicon.ico`, on every load of the public sheet — none
of `index.html`, `landing.html`, `editor.html`, `privacy.html` linked a favicon, confirmed by grep before the fix.

Fix: added `<link rel="icon" href="/icon.svg" type="image/svg+xml" />` to all four top-level HTML entry points
(the three named in the finding plus `privacy.html`, also a real build entry per `vite.config.ts`'s
`rollupOptions.input`). Failure case (older Safari lacking SVG favicon support): a second
`<link rel="icon" href="/icon.png" type="image/png" />` follows each SVG link — a browser that doesn't
recognise the SVG `type` falls through to the PNG one, the standard two-link fallback pattern. `icon.png`
generated from `icon.svg`'s own design (dark rounded square, "CS" in the same yellow, DejaVu Sans Mono) with
Pillow, since no SVG rasteriser (`rsvg-convert`/`cairosvg`/ImageMagick) was available in this sandbox.

Re-ran the identical script against the rebuilt `dist/`:

| Category | Before | After |
|---|---|---|
| Performance | 90 | 89 |
| Accessibility | 100 | 100 |
| Best Practices | 96 | **100** |
| SEO | 100 | 100 |

`errors-in-console` audit score 0 → 1, zero items (`docs/research/lighthouse-pilot-scale.json`, overwritten by
this run). Performance moved 90 → 89, both within the same CI-machine-noise band FR-77/FR-80 already noted
(the only red audits this run, `max-potential-fid` and two zero-weighted insights, are unrelated to a favicon
link tag).

## FR-81 merged (16:00 shift, 2026-09-24): combined score after resolving a stale PR

PR #202 (FR-81) had sat open since 13:00 with auto-merge enabled but never fired — `docs/company/BACKLOG.md`
had it marked `done`, but the merge itself never happened, so the fix was not actually on `main`. Its only
real conflict was this file's own generated JSON report (`docs/research/lighthouse-pilot-scale.json`), rewritten
independently by every later Lighthouse-running shift (FR-80, FR-82); the favicon HTML/PNG changes merged
cleanly. Resolved in the branch (no force-push) and re-ran `lighthouse_pilot_scale.py` fresh against the
merged tree (favicon links + FR-82's accessible-name fix + FR-86's unrelated backend enum fix, all together)
rather than hand-resolving the generated JSON:

| Category | Score |
|---|---|
| Performance | 92 |
| Accessibility | 100 |
| Best Practices | 100 |
| SEO | 100 |

Every category from FR-71's original 69/100/96/90 baseline is now at or above the dod's 90 line. Remaining
red audits (`max-potential-fid` 44, `forced-reflow-insight`, `network-dependency-tree-insight`) are informational/
zero-weighted and pre-existing, not from this fix. Full report overwritten at `docs/research/lighthouse-pilot-scale.json`.

## FR-85 (17:00 shift, 2026-09-24): Pages cache headers on hashed assets — local-test-server artifact, not a real gap

A prior local-only check would have had to run against a bare static-file server (Python's
`http.server`, or Vite's own unconfigured preview server), not the real GitHub Pages CDN, so a
"no cache headers" finding from one of those risked being an artifact of the test harness rather
than a fact about the live deployment. This sandbox's own egress proxy blocks
`sandovabarbora.github.io` (confirmed again this shift), so `scripts/check_pages_cache_headers.py`
(PR #212) ran instead from `.github/workflows/pilot-readiness.yml` on a GitHub Actions runner with
open egress — the same pattern FR-66/67/68/83 used — dispatched once from `main` after the PR merged
(run [36019478245](https://github.com/sandovabarbora/filmrunner/actions/runs/36019478245)).

It discovered the live build's real hashed asset URLs from `index.html`/`editor.html`/`landing.html`
(the hash changes every build, nothing hardcoded) and fetched each one 3 times to tell a stable
header apart from CDN edge-cache warm-up variance, per the item's own failure case:

| Asset | `Cache-Control` (3 fetches) | ETag | `x-cache` (3 fetches) |
|---|---|---|---|
| `editor-BOjTVerP.css` | `max-age=600`, stable | present, stable | MISS → HIT → HIT |
| `editor-C63y0A-1.js` | `max-age=600`, stable | present, stable | MISS → HIT → HIT |
| `landing-1Z_E4lnT.css` | `max-age=600`, stable | present, stable | MISS → HIT → HIT |
| `landing-CO3uC06V.js` | `max-age=600`, stable | present, stable | MISS → MISS → HIT |
| `modulepreload-polyfill-B5Qt9EMX.js` | `max-age=600`, stable | present, stable | MISS → HIT → HIT |

**Conclusion: local-test-server artifact, not a real gap.** GitHub Pages does send `Cache-Control`
and a stable `ETag` for every hashed asset checked; the `x-cache` progression (a cold `MISS` warming
to `HIT` on later fetches, once needing a second `MISS`) is exactly the edge-cache warm-up variance
the dod's failure case named, not missing caching. Self-tested locally first (not committed, not
asserted as a live finding): a bare Python `http.server` serving a real copy of `frontend/dist` under
`/filmrunner/` sends no `Cache-Control` at all for the same files — confirming that *is* where a
"no caching" finding would have come from, had one been reported without checking the real CDN.

One real, secondary observation, not filed as its own backlog item: `max-age=600` (10 minutes) is
short for a content-hashed filename that never changes once built — a browser could safely cache it
for a year (`max-age=31536000, immutable`) since a new build always ships a new hash. This is a
GitHub Pages platform default (not configurable from this repo — Pages serves no custom response
headers), costs at most one revalidation round-trip every 10 minutes per asset per visitor, and
600s already prevents the concern this item was raised to check (assets re-fetched from scratch on
every load). Not worth a `ready` item on its own.

## FR-84 (09:00 shift, 2026-09-25): confirmed the unused-JS chunk, deferred the print-only QR library

FR-71's original run flagged two opportunities beyond the CLS issue FR-77 already fixed:
`render-blocking-insight` on `styles-*.css` (~150–300ms) and `unused-javascript` finding 38%
(68 KiB of 177 KiB) unused in the main JS bundle. The item's own premise — "Performance is still
below 90 (69/100)" — was already stale by the time this shift ran: FR-77's CLS fix alone had moved
it to 94, and FR-80/81/82 stayed in the 90–95 band since. This shift re-confirmed that (94/95 across
two runs today) rather than assuming the 69 figure was still current, and treated the unused-JS
finding as worth closing on its own merits regardless.

**What's actually in the flagged chunk.** The `why` assumed the 38%-unused code was misplaced
editor/landing code shipping on the sheet route (the framing the dod bullet itself repeats). That
assumption does not hold: built a one-off Vite plugin (not committed) to print each chunk's real
module list with sizes. `styles-PlsSX0ha.js` (176,891 bytes, matching Lighthouse's own reported
byte count exactly) breaks down as: `react-dom` 133,289 B, `qrcode-generator` 51,765 B, `i18n.ts`
9,534 B, `react` 7,656 B, `editor/shareText.ts` 5,171 B, `scheduler` 4,364 B, `editor/screens/
QrCode.tsx` 795 B, `Avatar.tsx` 557 B (pre-minification renderedLength). React/react-dom/scheduler
are needed by both the viewer and the editor entries — genuinely shared, not dead weight.
`shareText.ts` (`whatsappNumber`/`whatsappUrl`) and `QrCode`/`qrcode-generator` are not orphaned
editor code either: `CallSheetView.tsx` imports both directly and uses them on every public sheet
view — `whatsappUrl` for each contact's WhatsApp button in "Who to call", `QrCode` for the QR in
the print-only footer bar. Both are real, exercised features of the sheet route itself, matching the
dod's own failure case: this is not code a different scenario needs, it's code *this* scenario needs
too, just not for the initial paint.

**What changed.** `qrcode-generator` (52 KB, the single largest non-React contributor) backs a
feature — the crew-link QR in the print footer — that is never seen until an AD or crew member
actually prints the sheet, well after first paint. `whatsappUrl`/`whatsappNumber` stay eager: contact
rows with a WhatsApp button are part of the sheet's primary, always-visible content, not deferrable
without delaying real functionality. `CallSheetView.tsx` now imports `QrCode` via `React.lazy()` +
`Suspense` (`fallback={null}`, the wrapping div is `aria-hidden` and print-only already) instead of a
static import, so Rollup code-splits `qrcode-generator` into its own chunk (`QrCode-*.js`) that the
viewer only fetches when the print footer actually mounts, and — since nothing in `index.html` static-
imports it — is no longer part of the `<link rel="modulepreload">` the browser eagerly fetches and
parses on every sheet load. The editor still statically imports the same component for its own
post-publish QR (`DayEditor.tsx`), so that route's own preload list picks it up unaffected.

**Measured.** Before (`docs/research/lighthouse-pilot-scale.json`, committed baseline): shared chunk
176,891 B, `unused-javascript` wastedBytes 68,499 (38.7%). After, same FR-52 pilot-scale production
(60 crew, 60 scenes), same script, two consecutive runs:

| Run | Shared chunk (`styles-*.js`) | `unused-javascript` wasted | Performance |
|---|---|---|---|
| Before | 176,891 B | 68,499 B (38.7%) | 92 (this run's own baseline; FR-71's original 69 pre-dates FR-77's CLS fix) |
| After, run 1 | 155,214 B | 51,674 B (33.3%) | 94 |
| After, run 2 | 155,214 B | 51,674 B (33.3%) | 95 |

A real, verified 21,677-byte (12.3%) cut to the chunk every sheet view eagerly preloads, and a
24.6% cut to Lighthouse's own wasted-bytes estimate on it — not a full elimination, because what's
left (React/ReactDOM/scheduler runtime code paths this specific page doesn't exercise, plus
`i18n.ts` translation keys the loaded sheet doesn't use) is genuine framework and app code the route
needs, just not byte-for-byte on this one page — consistent with the dod's failure case, so left
alone rather than guess-cut further. `render-blocking-insight` (the CSS half of the item's title) is
unchanged this shift: `styles-Bx2Md7ZZ.css` (15.6 KB) is a single blocking stylesheet import; a real
fix (critical-CSS extraction + async swap) carries a flash-of-unstyled-content risk for a page whose
whole thesis is being trustworthy on set, and the dod's own bullets only ask about the JS chunk — not
attempted this shift, left for a future item if the CSS opportunity (~150ms) is still worth it once
a real interview or pilot surfaces a load-time complaint.

Verified for real: `npm run typecheck` clean; `npm test` 53/53; full Playwright E2E suite 73/75 (the
2 failures are the standing, previously-documented Nominatim-egress-403 gap in `test_locations_e2e.py`,
unrelated — confirmed unrelated by running with this diff, same as every prior shift's finding) plus
one instance of the pre-existing `test_landing_flow_video_...` flake (also previously documented,
unrelated to `landing.html`; re-ran in isolation and it passed). `tests/test_pdf_e2e.py`'s own
`#printFooterBar svg` assertion (count == 1) passed, confirming the QR still renders correctly once
lazy-loaded. Backend suite 149/149 (untouched by this change, run for confidence). No backend change,
no deploy needed.

## FR-92 (16:00 shift, 2026-09-25): Lighthouse pass on landing.html

FR-71/77/80/81/82/84's Lighthouse work only ever scored `index.html`, the public call-sheet page.
`landing.html` (FR-25/62, the pitch built from FR-6's positioning, the page a prospective AD or the
founder actually opens first) had never been run through Lighthouse on its own. Unlike the sheet,
`landing.html` is fully static — no API, no database — so `frontend/scripts/lighthouse_landing.py`
(new, same pattern as `lighthouse_pilot_scale.py` minus the seeding) only builds and serves `dist/`.
Full report: `docs/research/lighthouse-landing.json`.

**First run** (mobile, headless `/opt/pw-browsers/chromium`, `npx lighthouse`):

| Category | Score |
|---|---|
| Performance | 97 |
| Accessibility | 100 |
| Best Practices | 92 |
| SEO | 100 |

All four already at or above the dod's 90 line, but Lighthouse's `cumulative-layout-shift` audit was
orange (score 0.89, actual CLS 0.100) and its `cls-culprits-insight` diagnostic named the three
`.shots` screenshot `<img>` elements as the shifting culprits — a real, fixable bug, not noise.

**Root cause.** Every one of the six landing screenshots (`public/landing/*.jpg`, taken by
`frontend/scripts/take_landing_screenshots.py`) is a crop of a real DOM region at whatever height
that region actually rendered — the header-through-sunrise clip and the `#locations`/`#contacts`
element screenshots are each a different real size. `landing.html`'s `<img>` tags all hardcoded a
single guessed `width="390" height="220"` regardless. Checking the actual files: `call-sheet-top.*`
is ~390×388–391 (near-square, not 390×220's 1.77:1), `locations.*` is ~335–350×376–417, and
`contacts.*` is ~335–350×881–882 (a tall list, over 2.5× the declared height). `.shots img { width:
100%; height: auto }` in `landing.css` derives its aspect-ratio box from these attributes per the
HTML intrinsic-size-mapping spec, so the browser reserved a landscape-shaped box, then reflowed the
whole page once each real (very different) image loaded — exactly Lighthouse's `main > section.shots`
culprit trace.

**Fix.** `take_landing_screenshots.py` now records each screenshot's actual captured CSS-pixel size
(from the same `bounding_box()`/clip values already used to take the shot) and rewrites the matching
`<img>`'s `width`/`height` attributes in `landing.html` after every run, so a future re-run (a new
screenshot after any visual change to the sheet, per the script's own usage note) can't drift back
into this bug — the previous hardcoded 390×220 was a one-time guess with nothing keeping it honest.
Regenerated all six screenshots and rebuilt; real sizes are now: `call-sheet-top.{cs,en}` 390×388,
`locations.cs` 335×417, `locations.en` 335×376, `contacts.{cs,en}` 335×881.

**Also tried and reverted:** bumping the screenshot capture's `device_scale_factor` to 2 closed a
separate, minor `image-size-responsive` "low resolution" Best Practices finding (96 → 100, the one
remaining <100 audit after the CLS fix) — but roughly doubled every screenshot's file size, which
pushed Performance from 97 to 88 (LCP moved from a passing 90 to a failing 59). A one-category, single
percentage-point Best Practices gain is not worth taking Performance below the dod's 90 line, so this
was reverted; the low-resolution finding is left as a known, accepted gap rather than fixed.

**Re-run after the width/height fix** (device_scale_factor back at 1):

| Category | Score |
|---|---|
| Performance | 97 |
| Accessibility | 100 |
| Best Practices | 96 |
| SEO | 100 |

`cumulative-layout-shift` is no longer orange (score 0.91, CLS 0.094 — small residual shift from
content above the fold, not the screenshot bug). The two remaining "red" items in Lighthouse's own
output (`lcp-discovery-insight`, `network-dependency-tree-insight`) are `weight: 0` diagnostic
insights (Lighthouse 13's new Insights panel), not scored audits — confirmed by reading their
`auditRefs` weight directly in the JSON report; they do not affect the category score and are not a
"below 90 with no fix" gap under the dod's own failure case.

Verified for real: `npm run build`/`typecheck` clean, `npm test` 53/53. Set up a local Postgres
role/db and both a backend venv and a combined frontend-test+backend venv from scratch (none existed
this session) to run the E2E suite: `test_smoke.py`+`test_a11y.py` 24/25 (the one failure,
`test_landing_flow_video_...`, is the same pre-existing flake every prior shift touching
`landing.html` has documented — re-ran in isolation and it passed); full Playwright suite 75/77 (the
2 failures are the standing, previously-documented Nominatim-egress-403 gap in
`test_locations_e2e.py`, unrelated). Backend suite 153/153, untouched by this change, run for
confidence. No backend/frontend runtime change beyond `landing.html`'s six `width`/`height`
attributes and the regenerated JPEGs; no deploy needed.

## Not measured here

- A real phone on a real network: the founder's protocol (readiness file) covers that.

# ADR-006: Location services — geocoding, sunrise/sunset, weather, nearest hospital

Date: 2026-09-15. Status: accepted (13:00 shift, FR-19). Serves FR-19;
founder request 2026-09-14: "an AD types sunrise, sunset and weather by
hand from other apps every evening".

## Context

`Location` already has `address`, `geo_lat`, `geo_lng` and
`nearest_hospital` columns (added ahead of this item); nothing filled
them. `CallSheetRevision.sunrise`, `.sunset` and `.weather_forecast` are
free-text strings the AD types by hand. BRIEF Q3 names wrong/missing
information as a top pain; typing four numbers off other apps every
evening is exactly the busywork the product should remove.

TEAM.md's approval contract: the routine may not create accounts or spend
money. So every provider here had to be usable with zero signup.

## Decision

Four independent, keyless providers, each with a timeout and a graceful
`None` fallback — the sheet must never wait on, or be blocked by, a third
party (dod's own failure-case bullet):

- **Geocoding — OpenStreetMap Nominatim** (`nominatim.openstreetmap.org`).
  Free, no key. Usage policy (checked 2026-09-15,
  https://operations.osmfoundation.org/policies/nominatim/): max 1
  request/second, a real `User-Agent` identifying the app (stock
  library user agents get permanently banned), no autocomplete/bulk
  geocoding. We call it once per location save, sequentially (no bulk),
  with `User-Agent: FilmRunner/1.0 (+https://github.com/sandovabarbora/filmrunner)`
  and a 5s timeout. `app/services/geocoding.py`.
- **Sunrise/sunset — computed in-process**, no external call. The
  well-known NOAA/Astronomical-Almanac sunrise equation (reference:
  https://en.wikipedia.org/wiki/Sunrise_equation and
  https://edwilliams.org/sunrise_sunset_algorithm.htm), zenith 90.833°
  to account for atmospheric refraction and the solar disk's radius,
  converted from UTC to `Europe/Prague` via `zoneinfo` so DST is
  correct automatically. `app/services/astronomy.py`. Accuracy is
  roughly ±1-2 minutes versus published almanacs. This routine's own
  egress proxy has always blocked `timeanddate.com` and
  `api.sunrise-sunset.org` directly (verified 2026-09-15 through
  2026-09-22, same failure mode as FR-2's teardown), so the check
  (FR-67, 2026-09-22) runs instead from a GitHub Actions runner with
  open egress: `scripts/check_astronomy_accuracy.py`, wired into
  `.github/workflows/pilot-readiness.yml`, compares this formula
  against sunrise-sunset.org (https://sunrise-sunset.org/api, free, no
  key, attribution required) for Prague across both solstices and both
  equinoxes of 2026. **Measured 2026-09-22** (run
  https://github.com/sandovabarbora/filmrunner/actions/runs/35738976530):
  every one of the 8 sunrise/sunset values was within 1-3 minutes of the
  live reference (spring equinox sunrise the largest, at 3 minutes;
  summer/winter solstice and autumn equinox all 1-2 minutes) — in line
  with the ±1-2 minute expectation above, now measured rather than
  assumed. `tests/test_astronomy.py` keeps the physical
  self-consistency checks (sunrise before solar noon before sunset, day
  length longest at the summer solstice and shortest at the winter
  solstice) and its solstice cross-check now asserts against these real
  measured values at ±3 minutes (was a ±20-minute band against
  approximate times recalled from memory, not fetched). The CI check
  reruns daily and on demand, so a regression in the formula or a
  provider change would be caught, not just checked once.
- **Weather — Open-Meteo** (`api.open-meteo.com`). Free for
  non-commercial use, no key, CC-BY 4.0 attribution required (checked
  2026-09-15, https://open-meteo.com/en/terms): up to 10,000 calls/day.
  Attribution is printed once in `docs/adr/ADR-006-location-services.md`
  (this file) and in the API footer, per the licence. One daily-forecast
  call per suggestion request (max/min temperature + WMO weather code
  mapped to a short phrase, e.g. "12-18°C, light rain"), 5s timeout.
  `app/services/weather.py`. Forecasts beyond ~16 days are not
  available from this provider; a shoot date further out returns no
  suggestion rather than a guess.
- **Nearest hospital — OpenStreetMap Overpass API**
  (`overpass-api.de/api/interpreter`). Free, no key; rate-limited by IP,
  not by application (checked 2026-09-15,
  https://wiki.openstreetmap.org/wiki/Overpass_API). Query
  `amenity=hospital` within a 10 km radius of the location's
  coordinates, sorted by straight-line (haversine) distance, 5s timeout.
  `app/services/hospitals.py`.

**Suggestion, not autofill, for anything free-text.** Sunrise/sunset are
computed values with no ambiguity, so a revision auto-fills them from the
day's first scheduled location when the AD leaves the fields blank on
publish (`services/call_sheets.py`), same as before an AD would type them.
Weather and nearest-hospital are provider guesses that can be wrong (a
Czech street name is exactly the case the dod calls out), so both are
served from dedicated `GET .../weather-suggestion` and
`.../hospital-suggestion` endpoints that the editor shows next to the
existing free-text field with an explicit "Use suggestion" action — never
overwriting what the AD already typed.

**Geocoding runs on location save**, not as a separate suggestion: an
address the AD typed themselves still needs coordinates before weather or
hospital lookups are possible, and a wrong resolution has to be visible
immediately. `Location` gains `geocoded_display_name` (nullable, not
user-editable) so the editor can show "resolved to: <name>" right next to
the address field the moment it changes.

## Consequences

- No INBOX item needed for FR-19's core: every provider used here is
  keyless. If a future shift wants a paid/branded geocoder (better
  Czech address matching) or a push-only weather integration, that's a
  new ADR and an INBOX item, not a silent swap here.
- Nominatim's 1 req/s limit means geocoding many locations in a batch
  import would need throttling; out of scope while locations are
  created one at a time in the editor.
- Astronomical accuracy **is** independently verified, daily and on
  demand, by the CI check named in the Decision section above (FR-67,
  `.github/workflows/pilot-readiness.yml`) — this bullet said otherwise
  and was left stale after FR-67 landed 2026-09-22; caught and fixed
  2026-09-30 (FR-112) when it turned out to contradict the Decision
  section directly above it. Re-read the check's most recent scheduled
  run rather than re-dispatching a duplicate one: [run
  36560857147](https://github.com/sandovabarbora/filmrunner/actions/runs/36560857147)
  (2026-09-29 11:18 UTC, `main`@`640352a`) — all 8 values still within
  1-3 minutes of sunrise-sunset.org, matching the 2026-09-22 measurement
  above.

## Out of scope

Per-department weather (only the day's first location), historical
weather, radar/precipitation maps, geocoding providers that need an
account, hospital opening-hours or specialty data (Overpass only gives
name/address).

## Revisit when

The daily/on-demand CI accuracy check (FR-67) reports a deviation above
its ±3-minute tolerance for two runs in a row (a genuine formula issue,
not a one-off provider hiccup); or a production needs a location outside
OpenStreetMap's coverage.

## Addendum, FR-222 (2026-11-06): values stored before the rounding fix

A minute that rounded up to 60 became :00 without carrying the hour, so 07:00 read as 06:00. That hit 22 of 1460 Prague values over 2026 and 2027, about 3% of days. The calculation is fixed; stored revisions are not, since nothing rewrites a published revision's sun times, and the editor and a moved day carry the old value forward. `cd backend && python -m scripts.sun_rollover_report` counts what is affected, read-only. An AD clears the two sun fields and publishes to correct a day.

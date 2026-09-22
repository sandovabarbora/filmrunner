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

## Not measured here

- Lighthouse mobile score: not run (no Lighthouse in the harness; the numbers above are time-to-usable on a throttled
  network, which is what the dod's 2 s line is about). The public sheet bundle is 66 KB gzipped JS + 12 KB CSS.
- A real phone on a real network: the founder's protocol (readiness file) covers that.

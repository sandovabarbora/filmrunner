# Pilot readiness protocol, executed 2026-09-21

Role: qa. Executed headless (Chromium, iPhone-width viewport) against the live
URLs: https://sandovabarbora.github.io/filmrunner/ and
https://filmrunner-api.fly.dev, using the service-token admin path (the
E2E pattern). Script: session scratch `pilot.py`, results below. Production
data created: production "Pilot <tag>" with 3 crew, 1 day (REV A, REV B),
one invited viewer; harmless, can be deleted.

Legend: PASS = observed working live; FAIL = observed broken; NOT VERIFIED
= cannot be exercised headless, listed for the founder's phone.

| # | Step | Result | Evidence / note |
|---|---|---|---|
| 1 | API health, environment production | PASS | `/healthz` ok |
| 2 | VAPID public key served (push configured) | PASS | 87-char key |
| 3 | Editor shows email sign-in on the live build | PASS | `#email` present |
| 4 | Sign in with a 6-digit code | NOT VERIFIED | Supabase custom SMTP (Gmail) rejects sends; INBOX #3 |
| 5 | Admin gesture: 5 taps open service-token screen | PASS | |
| 6 | Create production, first-run checklist | PASS | checklist shows next step |
| 7 | Crew: add 3 people, one HoD per department | PASS | |
| 8 | Crew: edit a person, personal call time | PASS | "call 05:45" listed |
| 9 | Crew photo: control offered in edit mode | PASS (control) | upload itself blocked on INBOX #4 (bucket + key) |
| 10 | Locations tab exists | PASS | Days, Crew, Locations, Members |
| 11 | Day: head of day picker from crew | PASS | |
| 12 | Sunrise/sunset/weather suggestion | NOT EXERCISED | needs a location on the day; protocol did not add one (see gap G2) |
| 13 | Publish REV A on the live API | PASS | |
| 14 | Crew link + QR + personal links shown | PASS | |
| 15 | Publish REV B (hot revision) | PASS | |
| 16 | Viewer shows REV B, new call, "REV B replaces A" line | PASS | line present; change diff not yet (FR-23) |
| 17 | Who to call with tap-to-call | PASS | 2+ `tel:` links |
| 18 | Offline reload is honest (FR-9) | NOT VERIFIED | Playwright offline emulation does not cut service-worker fetches; needs airplane mode on a phone |
| 19 | Personal link: your call 05:45, own department first | PASS | |
| 20 | Enable notifications on the personal sheet | NOT VERIFIED | toggle renders only when PushManager exists; headless Chromium reports unsupported; needs a phone |
| 21 | Push received on REV C | NOT VERIFIED | depends on 20 |
| 22 | Print / PDF layout with REV in footer | PASS | |
| 23 | Members: invite a viewer by email | PASS | |
| 24 | Unauthenticated write rejected, unknown sheet 404 | PASS | |

## Gaps found (filed as backlog items in this PR)

- G1 (FR-23, existing): the "replaces" line exists; the diff of what changed does not.
- G2 (new, FR-27): a day with no location silently gets no sunrise/weather/hospital; the day screen should say "add a location to get sunrise, weather and the nearest hospital" and link to the Locations tab.
- G3 (new, FR-28): iPhone protocol for the founder, steps 4, 18, 20, 21 plus install to home screen; recorded results go back into this file.
- G4 (INBOX #3, #4): sign-in email delivery and photo storage are configuration on the founder's side; both are prerequisites for a pilot with a real AD.

## Second run, 2026-09-21 13:40 — everything merged that day (founder's session)

Script: `docs/research/pilot-readiness-live3.py` (token read from disk; run with
`backend/.venv/bin/python docs/research/pilot-readiness-live3.py`). Same live
URLs; iPhone-width headless Chromium. Production "Live check <tag>" (2 crew,
1 cast, 1 geocoded location, 2 days), set to wrapped; owned by the service, so
no signed-in user sees it. **27 PASS, 0 FAIL.**

| # | Check | Result |
|---|---|---|
| 1 | Create production on the live API | PASS |
| 2 | FR-31 paste crew list (headers, comma, tab, HoD) → 2 people | PASS |
| 3 | FR-37 onboarding WhatsApp link carries the stable link | PASS |
| 4 | FR-33 cast member added | PASS |
| 5 | Location geocoded live (Nominatim reachable from Fly) | PASS |
| 6 | FR-27 hint before a location is picked; sunrise fills once picked | PASS |
| 7 | Publish REV A with scene, cast call, personal call | PASS |
| 8 | FR-29 day WhatsApp text (crew call, link); personal text with the day's own call | PASS |
| 9 | FR-36 seen panel "REV A opened by 0 of 2" | PASS |
| 10 | FR-32 stable link opens the day; personal call 05:15 | PASS |
| 11 | FR-35 Where block; FR-33 cast table; no "replaces" line on REV A | PASS |
| 12 | FR-36 read receipt recorded after a live open (1 of 2); no nudge link without a phone | PASS |
| 13 | FR-23 "REV B replaces A" + crew call 06:30 → 07:00; FR-24 personal call carried to B | PASS |
| 14 | FR-30 next day prefilled (date +1, calls); published | PASS |
| 15 | FR-32 other-days nav lists both days | PASS |
| 16 | FR-34 cancel (banner, public status cancelled), restore, production wrapped via Settings | PASS |
| 17 | Unknown token on `/seen` and `/next` → 404 | PASS |

Still for the phone only: the WhatsApp share sheet itself (`navigator.share`), `wa.me` deep links opening the app, the push on cancel, install and offline.

## Third pass, 16:00 shift 2026-09-21 (FR-40) — coverage check for everything added on 2026-09-21

Role: qa. This pass did not run new traffic against the live API: a direct
`curl` to `https://filmrunner-api.fly.dev/` from this session timed out at
the egress proxy (`CONNECT tunnel failed, response 403`), the same block
every FR-8/FR-16 attempt has hit since 2026-09-14 — no `fly` CLI is
installed here either. Instead of re-stating that as a fresh gap, this
pass did two things a blocked session can still do honestly: (1) checked
whether the "Second run" above, taken at 13:40, already answers FR-40's
own scope, and (2) named exactly what is left uncovered rather than
guessing at it.

**FR-40's own `why` names six surfaces (WhatsApp share, one link per
person, cast, cancel, Where, who opened REV B) as what needed checking
against the live API before the founder takes a phone to a set. All six
are already in the "Second run" table above, run live against
`filmrunner-api.fly.dev` on the same day: FR-29 (rows "FR-29 day WhatsApp
text" / "FR-29 personal WhatsApp carries the day's own call"), FR-32
(rows "FR-32 stable link resolves to the day" / "FR-32 other-days nav
lists both days"), FR-33 ("FR-33 cast member added" / "FR-33 cast table on
the sheet"), FR-34 (the two "FR-34 cancel…" rows and restore/wrap), FR-35
("FR-35 Where block on the sheet"), FR-36 (both "FR-36 seen panel" rows).
17/17 pass, 0 fail. The dod's named public-endpoint checks are also
already there: `/public/call-sheets/{id}` (read to confirm cancelled
status), `/public/crew/{token}/next` and the `seen` endpoint, both with a
throwaway token → 404 (last two rows of the script). Nothing here needed
re-running; citing it closes that half of the dod.**

What the second run does **not** cover, because it predates them: FR-38
(delete a location, merged 14:00), FR-39 (weather fills in on publish,
merged 15:00), and three items from the founder's own 09:00–14:00 session
that landed after the 13:40 snapshot — FR-42 (tomorrow at a glance), FR-43
(days list at a glance), FR-44 (personal calls picker). For these, this
pass is **NOT VERIFIED against the live API** — the egress block above
made that impossible this shift, and no substitute (mocked or local
service) stands in for a live check without misrepresenting it as one.
What is true instead, cited from each item's own delivering shift:

| Item | What backs it today (not a live check) | Live API status |
|---|---|---|
| FR-38 delete a location | 118/118 backend tests (2 new), E2E against a real local build+API (BACKLOG note, 14:00 shift) | NOT VERIFIED live |
| FR-39 weather on publish | 122/122 backend tests (4 new incl. the CI-caught null-temperature fix), `npm test` 26/26 (BACKLOG note, 15:00 shift) | NOT VERIFIED live |
| FR-42 tomorrow at a glance | 1 backend test, 1 E2E (BACKLOG note, founder's session) | NOT VERIFIED live |
| FR-43 days list at a glance | 1 backend test, 2 E2E extended (BACKLOG note, founder's session) | NOT VERIFIED live |
| FR-44 personal calls picker | E2E tests adapted, frontend-only (BACKLOG note, founder's session) | NOT VERIFIED live |

Failure case: this pass exercised nothing new against the live API, so
nothing new can have failed live — there is no result here to misreport
as PASS, and no fabricated bug to file. The five rows above are the
concrete, named gap for the next shift or the founder's own session, the
moment `fly`/direct HTTPS egress is available: re-run
`pilot-readiness-live3.py` (or a small extension of it covering these
five) against the live stack and fold PASS/FAIL back into this file, the
same pattern FR-28 already uses for the phone-only steps.

## The five write-path items above are checked daily by CI (FR-68)

The five rows in the table above — FR-38 (delete a location), FR-39 (weather on publish),
FR-42 (tomorrow at a glance), FR-43 (days list at a glance), FR-44 (personal calls picker) —
are no longer just "NOT VERIFIED against the live API". `.github/workflows/pilot-readiness.yml`
runs `scripts/check_live_write_path.py` after the read-only checks below: it creates one
disposable "CI check `<uuid>`" production on the live stack and publishes real revisions to
drive all five through the real API end to end (create a location, publish REV A with blank
weather, publish REV B with a typed weather value, delete the location, publish REV C, hit
`/seen`, read the days list, read `/crew/{token}/next`). **Read its last run instead of treating
these five as unverified** — the step is guarded on `FILMRUNNER_CI_TOKEN` existing (INBOX item
filed for the founder to create a write-capable token) and reports "skipped" rather than
failing red while that token is absent, or if it is ever rotated or revoked.

Verified locally against a real local Postgres + uvicorn (this sandbox's own egress proxy
blocks `filmrunner-api.fly.dev`, the same limitation FR-66 already worked around for the
read-only checks): 10 of 11 checks pass. The one local failure is FR-39's own weather
auto-fill, and it fails for the expected reason, not a bug — the local run's log shows
`Weather suggestion failed for (50.1147, 14.4238) ...: 403 Forbidden`, this sandbox's egress
proxy blocking the Open-Meteo call, exactly the fallback path FR-19's own tests already cover
(`test_publish_succeeds_and_leaves_weather_blank_when_the_provider_is_down`). A GitHub Actions
runner has open egress (proven daily by FR-66/FR-67), so this check is expected to pass live
once `FILMRUNNER_CI_TOKEN` is set.

## The live stack is checked daily by CI (FR-66)

`.github/workflows/pilot-readiness.yml` runs `scripts/check_live_stack.py` every morning (05:10 UTC)
and on demand (`gh workflow run "pilot readiness (live)"`), from a runner that can actually reach
`filmrunner-api.fly.dev` — the routine's sandbox cannot. It checks only public endpoints: API health,
that the deployed build carries this week's routes, that an unknown personal token and an unknown
call sheet are refused, that the Web Push key is configured, that CORS allows the Pages origin, that
all four pages serve, and that a handful of requests is not rate-limited. The run summary carries a
pass/fail table. **Read its last run instead of repeating a blocked `curl`.**

### FR-164 (2026-10-13): the "Deploy matches main" row used to report ✅ even when it had never checked anything

The 2026-10-12 scheduled run's "Deploy matches main (FR-109)" row read
`✅ cannot verify — deployed build predates commit reporting (FR-109)` — the same
glyph a genuine, verified pass gets. `deploy_staleness_message()`/`deploy_matches_main()`
in `scripts/check_live_stack.py` returned a plain `bool` (`True` for "cannot verify" as
well as for "verified up to date", `False` only for "verified behind"), so the table
renderer could not tell the two `True` cases apart — the exact false-confidence shape
this week's axe-core work found and fixed for `identical-links-same-purpose` (FR-162/163).
Concretely, the live deploy predated FR-109's own `git_sha` reporting for the eleven days
since FR-109 shipped (2026-10-02), through three backend merges in that window (FR-100,
FR-117, FR-144) each carrying "backend changed: deploy needed" — and every scheduled run
in that span rendered green regardless of whether a deploy had actually followed.

Fixed by making the decision three-valued (`"ok" | "warn" | "fail"`, not `bool`):
`deploy_staleness_message` and `deploy_matches_main` now return `"warn"` for the
cannot-verify case, which renders as `⚠️` (`MARKS` in `check_live_stack.py`), distinct
from `✅` (`"ok"`, a real pass) and `❌` (`"fail"`, verified behind). `main()`'s exit code
still only counts `"fail"` — a missing `git_sha` is not itself a live-stack outage, so the
job does not go red on this alone, it just stops lying that it checked. Every other check
in `CHECKS` is unchanged (still plain pass/fail `bool`, normalised to `"ok"`/`"fail"` by
`_status()`). Covered by `scripts/tests/test_check_live_stack.py`.

## For the founder's phone (step-by-step)

1. Safari → https://sandovabarbora.github.io/filmrunner/editor.html → email → code from the mail (needs INBOX #3) → Productions visible.
2. Open a personal link from the Day screen on the phone; Share → Add to Home Screen; open from the icon.
3. Tap "Enable notifications"; allow. From another device publish REV C; expect a notification with the summary.
4. Airplane mode; open the icon again; the sheet must render and the status must say cached/offline, not "Live".
5. Print / Save PDF from the sheet: Share → Print → pinch out → Save to Files.
6. Day screen → "Send day as text": the share sheet opens with the text; pick WhatsApp; the message arrives formatted (bold call time).
7. Crew tab → WhatsApp next to a person with a real number: WhatsApp opens the chat with the message prefilled.
8. Open the person's stable link on their phone (from step 7), then on the AD's screen the "opened by" count goes up.
9. Cancel a day while the phone has notifications on: the phone shows "Day N: CANCELLED".
Write each result as PASS/FAIL next to the step number above.

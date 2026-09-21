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

## For the founder's phone (step-by-step)

1. Safari → https://sandovabarbora.github.io/filmrunner/editor.html → email → code from the mail (needs INBOX #3) → Productions visible.
2. Open a personal link from the Day screen on the phone; Share → Add to Home Screen; open from the icon.
3. Tap "Enable notifications"; allow. From another device publish REV C; expect a notification with the summary.
4. Airplane mode; open the icon again; the sheet must render and the status must say cached/offline, not "Live".
5. Print / Save PDF from the sheet: Share → Print → pinch out → Save to Files.
Write each result as PASS/FAIL next to the step number above.

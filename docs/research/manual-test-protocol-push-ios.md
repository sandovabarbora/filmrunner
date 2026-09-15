# Manual test protocol: Web Push on a real iPhone

FR-16, ADR-007. This shift's environment has no physical iPhone and no
network path to Apple's push service, so the automated suite (backend:
`backend/tests/test_push.py`; frontend: `frontend/tests/test_push_e2e.py`)
mocks the two browser APIs a real device provides — this protocol is the
part only a real phone can confirm. Run it once before relying on push for
a live shoot day, and again after any change to `frontend/public/push-sw.js`
or the subscribe flow in `frontend/src/push.ts`.

Needs: an iPhone on iOS 16.4 or later, the deployed FilmRunner URL
(GitHub Pages once FR-8/INBOX #2 is live), and the VAPID keys set on the
API (INBOX #5) — without them the "Enable notifications" control does not
appear at all, by design (see ADR-007's Gating section).

## Steps

1. **Install as a home-screen app.** Open a crew member's personal link
   (`?sheet=...&api=...&me=...`) in Safari. Tap Share → *Add to Home
   Screen*. iOS does not expose `PushManager` to an ordinary Safari tab —
   this step is not optional.
2. **Open the installed app**, not the Safari tab. Confirm the personal
   "Your call" block renders (proves FR-13 still works from the installed
   app, not just the browser).
3. **Enable notifications.** Tap "Notify me when this call sheet
   changes." iOS shows its own permission prompt; allow it. The control
   should switch to "🔔 Notifications on for this device" within a couple
   of seconds. If it shows an error instead, capture the exact text — it
   is a real failure to record, not a console-only concern (there is no
   console on a phone).
4. **Publish a revision from another device** (the editor, e.g. a laptop)
   for the same call sheet: change the crew call time and publish REV B.
5. **Confirm delivery**, with the installed app closed (backgrounded or
   fully killed, not just the tab):
   - A system notification appears within roughly 30 seconds, titled
     `Day N: REV B`, body `REV B replaces A: crew call HH:MM`.
   - Tapping it opens the installed app directly to this call sheet
     (not Safari, not the home screen), already showing REV B.
6. **Confirm the sheet itself** also shows the "REV B replaces A" line
   (this part *is* covered by the automated suite, but worth re-checking
   in the actual installed-app rendering, which can differ subtly from
   desktop Safari's viewport).
7. **Turn notifications off.** Tap "Turn off". Publish another revision
   (REV C) from the editor. Confirm no notification arrives this time —
   turning it off must actually stop delivery, not just change the label.
8. **Record the result** (device, iOS version, pass/fail per step, any
   deviation) as a dated entry appended below this line, so the check
   stays current as the OS and the app both change. Do not overwrite a
   prior entry — append.

## Results log

_(none yet — this shift could not run the protocol; append the first real
run here)_

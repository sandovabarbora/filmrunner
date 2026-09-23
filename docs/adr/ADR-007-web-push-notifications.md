# ADR-007: Web Push for revision notifications

Status: accepted, partially gated (see below)
Date: 2026-09-15

## Context

FR-16: "crew missing an update" is the exact failure BRIEF.md Q3 names as
the wedge's reason to exist — a revision nobody is told about is a PDF
with extra steps. A crew member needs to know the moment an AD publishes a
new revision, without having to reopen the link and compare by hand.

The candidate approaches:

1. **Web Push (VAPID)** — the browser-native push API. A subscribed
   service worker gets woken by the OS even when the tab/PWA is closed,
   and shows a system notification. No account: VAPID (RFC 8292) is a
   self-issued EC keypair the server uses to sign its own identity; the
   browser's own push service (Google's for Chrome, Mozilla's for
   Firefox, Apple's for Safari/iOS 16.4+) delivers the message using the
   subscription URL the browser handed out. Nothing to create, nothing to
   pay for.
2. **Firebase Cloud Messaging (FCM)** — needs a Google/Firebase project
   (an account), and for iOS specifically still routes through Apple's
   push service underneath; adds a dependency on Google's console for no
   capability Web Push doesn't already give us on the browsers we target.
3. **SMS** — reaches a feature phone too, but needs a paid provider
   account (Twilio or similar) and per-message cost; out of scope per the
   dod ("fallback channels are designed but not built; any account or
   paid service is an INBOX item").
4. **Email** — Supabase's built-in mailer is already rate-limited to
   2/hour (INBOX #3) and email is not "in your pocket" the way a phone
   notification is; also out of scope for this item.

## Decision

Web Push with VAPID, using `pywebpush` (which wraps `py-vapid` for JWT
signing and `http_ece` for the RFC 8291 message encryption) on the
backend, and the browser's native `PushManager` / `Notification` APIs on
the frontend. No new account, no INBOX item for the transport itself —
only for the deploy step that makes it live (see Gating below).

### Data model

`PushSubscription` (new table): one row per browser/device a crew member
opted in from — `crew_member_id`, `endpoint` (unique — a browser's own
push-service URL), `p256dh` and `auth` (the browser's encryption keys for
this subscription), `link_url` (the exact crew/personal link that page
was opened with, so the notification's tap-through works without the
backend having to know the frontend's deployed origin — GitHub Pages
today, something else later), `created_at`.

`DistributionLog` gains a `push` value on its existing `channel` enum and
a new nullable `error` column. Every notification attempt — success or
failure — writes one row, keyed to the crew member's `contact_id` and the
revision. This is the dod's failure case: the AD can see exactly who did
not get REV B, not just infer "some pushes probably failed".

### Where subscribing happens

A crew member opts in from their own personal link (`?sheet=..&me=<token>`),
never from the editor — the AD cannot subscribe someone else's phone.
`link_url` is captured client-side at subscribe time (the page's own
`location.href`) rather than reconstructed server-side, so the backend
never needs to know the frontend's deployed origin.

### Where sending happens

Synchronously, inside the publish-revision request, right after the
revision is written. At pilot scale (a handful of crew per production)
sending a few HTTPS calls to push services adds low tens of milliseconds
per subscriber to the publish response; this is a documented shortcut, not
an oversight — a production large enough for this to matter should move
sending to a background job, which is a straightforward follow-up (the
send call is already isolated in `app/services/push.py` and does not touch
the DB session beyond writing `DistributionLog` rows).

### Message

`"New call sheet: crew call 07:30"` for the first revision (A), or
`"REV B replaces A: crew call 07:30"` for a correction — the same line the
sheet itself now shows (also serves FR-11's "hot revision" note). The
notification's `data.url` is the subscriber's own `link_url`, so tapping
it opens their personal sheet directly, already showing the new revision.

### Delivery failure

`pywebpush` raises `WebPushException` with the push service's HTTP status
on any non-2xx response. A `404`/`410` means the browser itself revoked
the subscription (uninstalled, cleared data, or another app on the same
push service moved on) — that subscription row is deleted so the next
publish doesn't keep retrying a dead endpoint. Every other failure keeps
the subscription (it might be transient) and is logged with the reason.

### Notification-worthy: not building

Fallback channels (SMS, email-per-revision) are explicitly **not built**
this shift, per the dod. If a production ever needs them, they would need
a paid provider account — an INBOX item at that time, not now.

## Gating (why this item is `gated: partial`)

Everything above needs no account and ships in this PR. What does need
the founder:

- **VAPID keys as Fly secrets.** `backend/scripts/generate_vapid_keys.py`
  prints a fresh keypair to the terminal (never to a file, never to the
  repo); the founder runs it once and sets
  `FILMRUNNER_VAPID_PUBLIC_KEY` / `FILMRUNNER_VAPID_PRIVATE_KEY` /
  `FILMRUNNER_VAPID_SUBJECT` (a `mailto:` contact the push services may
  use to reach the site operator — RFC 8292 requires one) via
  `fly secrets set`. Filed as INBOX #5.
- Until those secrets exist, `GET /api/v1/public/push/vapid-key` returns
  `{"public_key": null}` and the frontend simply does not offer the
  "Enable notifications" control — the same "visible but inert until
  configured" pattern FR-18's photo upload uses for the Supabase Storage
  secret, not a broken button.

## iOS support

Push for a home-screen-installed PWA has shipped on iOS since **Safari
16.4** (WebKit release notes, checked 2026-09-15:
https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ —
"Web Push ... for Home Screen web apps" ships in Safari 16.4, March 2023).
Two iOS-specific constraints that the failure case above already covers
generically:

- The PWA must be added to the home screen first — Safari does not expose
  `PushManager` to an ordinary browser tab on iOS. `push.ts` checks
  `"PushManager" in window` and `"serviceWorker" in navigator` before
  showing the control, so on an un-installed iOS Safari tab the control is
  simply absent rather than throwing.
- iOS notifications require the user to have granted the *site* permission
  as well as the OS-level notification permission for the installed app;
  a denial surfaces through the same `Notification.requestPermission()`
  path as every other browser, so no iOS-specific branch is needed.

This shift could not exercise the above on a real iPhone (no device
available in this environment); `docs/research/manual-test-protocol-push-ios.md`
records the steps for whoever runs the pilot to do that check for real
before relying on push for a live shoot day.

## Consequences

- No INBOX item was needed to build this (unlike FR-8's Fly/Supabase
  accounts or FR-18's Storage bucket) — only to turn it on in production.
- Sending is synchronous with publish; revisit if a production's crew
  count makes publish latency noticeable (a background queue is the
  obvious next step, not a redesign).
  - **Measured 2026-09-23 (FR-72), `backend/tests/test_push_scale.py`, 50
    subscribers (within the 40-60 pilot-scale range):** this codebase's own
    per-subscriber overhead — the ORM query, one `DistributionLog` row per
    subscriber, one commit, with `webpush()` mocked to return instantly —
    is 89 ms total, not the bottleneck. But that number excludes the one
    thing this trigger is actually about: a real HTTPS POST to a push
    service. This sandbox has no live push service and no real subscribed
    device (every FR-16-era shift note says the same), and a targeted
    `WebSearch` this shift for a published "typical" Web Push endpoint
    latency turned up nothing more specific than "under one second" (the
    IETF `webpush-protocol` draft's push-window discussion) — not a number
    worth treating as fact. So the trigger is **not closed with a verified
    real-world figure**; instead, a stated assumption (150 ms/request, a
    conservative low end for one synchronous HTTPS POST — the same order of
    magnitude this module's own `_SEND_TIMEOUT_SECONDS = 5` treats as a
    generous upper bound) projects **~7.7 s** of added, in-request latency
    for 50 subscribers, because the loop in
    `app/services/notifications.py`'s `_notify` is strictly serial. Even at
    the low end of a plausible real latency, that is long enough for an AD
    to notice "Publish" hanging. A representative measurement instead needs
    either a live pilot with real subscribed devices, or a local server
    that injects realistic connection/TLS/response delay — neither exists
    yet. Given the projection is not reassuring even as a floor, this is
    treated as the "noticeable" branch of the trigger: **FR-78** files the
    follow-up (deliver notifications from a background task after the
    publish response returns) rather than redesigning now.
- `link_url` trusts the client to report its own URL truthfully at
  subscribe time; this is the same trust boundary the personal-token
  link itself already carries (anyone with the link can already read the
  sheet), so it adds no new exposure.

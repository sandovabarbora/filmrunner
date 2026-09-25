# First pilot: plan (proposal, 2026-09-25)

Proposal for the founder to accept, change or reject. Nothing here changes
TEAM.md or the shift routine by itself.

## Why now

The hackathon week (2026-09-21 to 25) made the product pilot-ready on paper:
85 backlog items done, the full AD loop passes on the live stack
(`docs/research/pilot-readiness-2026-09.md`, 27/27). What is missing is not a
feature. No AD outside the company has used it, no FR-3 interview has
happened, and the four phone-only readiness steps (code sign-in, offline
reload, enable push, receive push) are still not verified. The BRIEF's kill
criteria cannot be tested until someone real uses it.

Meanwhile the hourly shifts refill the backlog with work that cannot be
checked against a user (desk-research re-verification, Lighthouse scores on
pages nobody has visited). This plan swaps that for one real production.

## Week 0: unblock (founder, about two hours in total)

1. INBOX #3: custom SMTP for sign-in. Without it nobody new can sign in, and
   the only fallback is the shared service token, which is owner on every
   production and must never sit on a pilot AD's phone.
2. `fly deploy` from the Mac: FR-78 (background push) and FR-86 (push
   delivery logging enum) merged on 2026-09-24 and are not live yet.
3. FR-28: run `docs/research/manual-test-protocol-push-ios.md` on your own
   iPhone. Offline reload and push are the positioning; they must be seen on
   a real phone before a real crew relies on them.
4. FR-91 (dependency scan) before real crew phone numbers go in. It is the
   one item of this week's queue worth keeping.

## Week 1: five conversations, each also a pilot offer

INBOX #1. Use the FR-3 script in `docs/research/discovery-plan.md` and the
outreach text in `docs/marketing/pilot-outreach.md`. Each conversation ends
with one question: "Do you have a shoot in the next four weeks where we could
run the call sheet through FilmRunner, with me on call?"

Apply the BRIEF kill criteria as written: if fewer than 2 of 5 name
call-sheet distribution among their top-3 pains, stop and re-frame before
any pilot.

## Weeks 2 to 3: one production, at least three shoot days

- Day 0 evening: sign the AD in, import crew, publish REV A together
  (`docs/pilot/onboarding-ad.md` is the script).
- Day 1: founder on set or on the phone from crew call. Write down every
  workaround, every question, every moment someone falls back to a PDF or a
  WhatsApp group message. That list is the next backlog, not our guesses.
- Days 2 and later: the AD publishes alone. The founder only watches the
  numbers below.

## What we measure

All three come from data the app already stores (`revision_views`, one row
per person per revision, with `first_seen_at`). No analytics are needed.

| Metric | How it is read | Target by day 3 |
|---|---|---|
| Crew who opened their personal link before their own call time | `first_seen_at` < call time (personal call, else crew call) for the current revision, over crew with a personal link | ≥ 80% |
| REV B (and later) opened within 30 minutes of publishing | `first_seen_at` − revision `created_at` | ≥ 70% |
| The AD publishes day 2 and later without help, and never sends a parallel PDF or WhatsApp sheet | Founder's day log plus asking the AD | yes / no |

Caveat: a view counts only when a personal link loads live. The shared crew
link and cached reloads are not counted, so the first two numbers are a lower
bound.

## What the shifts do during the pilot

A proposal, not yet a decision:
- Feature freeze. Only fixes that come out of the pilot log, plus
  anything that blocks a shoot day.
- Pause or thin out the self-refilling hourly shifts. One daily brief that
  reads the pilot numbers is enough.
- Shelve FR-87 to FR-90, FR-92 and FR-94 (desk research, Lighthouse, zoom)
  until after the pilot. Their `state` stays `ready`, just below the pilot
  items.

## Decision points

- After week 1: kill criteria met? If not, re-frame the wedge (BRIEF).
- After pilot day 3: are the metrics near target? If yes, a second
  production and a pricing conversation (Q4 ladder). If no, the day log tells
  us whether it is the product, the onboarding, or the wrong user.

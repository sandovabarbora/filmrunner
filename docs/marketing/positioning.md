# Positioning draft

FR-6. Role: marketing. Date: 2026-09-21. Grounded in `BRIEF.md` (v0.1,
including its 2026-09-18 hypothesis rewrite from the real June 2026 source,
PR #81) and `docs/research/competitive-teardown.md` (FR-2, 2026-09-14),
cross-checked against `docs/research/switching-cost-teardown.md` (FR-21,
2026-09-18).

## Status of this draft

This is a hypothesis for FR-3 to test, not a validated claim. FR-3
(five Prague interviews) is still blocked on the founder recruiting
candidates (INBOX #1) — nothing below has been said back to a real AD or
production coordinator yet. `BRIEF.md`'s kill criterion applies here too:
if fewer than 2 of 5 FR-3 interviewees name call-sheet distribution among
their top-3 pains, this positioning is stale along with the wedge it rests
on and needs re-framing, not defending.

## Alternatives considered

**1. AI speed: "script to a call sheet in everyone's pocket in 30
minutes."** This is the June 2026 source brief's own differentiation
claim (`BRIEF.md` H4, citing the source's "nobody can demo this today —
not Movie Magic, not StudioBinder, not Yamdu"). Rejected for now: nothing
in this repo's actual backlog builds script-to-breakdown AI drafting —
`docs/adr/ADR-001-backend-stack.md` (FR-4) names it explicitly as
something the old repo had that this skeleton does not yet, and
`BRIEF.md`'s own "out of scope until v1" section excludes new product
features. Leading with a capability we cannot demo would be a claim the
product cannot back up in a pilot. Parked, not deleted: if Q7's MVP-shape
scoring (once FR-3 data exists) picks "generation from an existing
schedule" as the smallest wedge, this becomes the lead claim, not a
supporting one.

**2. Delivery tracking: "never miss a revision — see who has and hasn't
opened it."** Real and built (FR-16 logs delivery per crew member,
including failures). Rejected as the *lead* position: FR-2's teardown
found StudioBinder and Croogloo already build read/open/bounce tracking as
a core, advertised feature — this is table stakes to be taken seriously as
a replacement, not a wedge (`competitive-teardown.md`, "What this means
for BRIEF.md's open questions"). Keeps a supporting role: without it, the
chosen position below is not credible either.

**3. Local: "built for Prague / Czech productions."** Still rejected as the
lead position, now on FR-20's actual finding rather than an open question.
FR-20 (`docs/research/prague-market-sizing.md`, 2026-09-21) answered
BRIEF.md Q5, but with an order-of-magnitude estimate, not a count: no
public source publishes the 30-day active-production figure Q5 asks for,
so FR-20 built one from proxies (~88 Czech films completing per year,
several large foreign productions confirmed overlapping the current
window, a real but unquantified annual FAMU output) and put the
Prague-region count of active productions in any 30-day window at "low
tens to low hundreds," with large uncertainty on the top end because the
most numerous category — student, ad, and micro-budget shoots — is
exactly what none of the sources track. Measured against a commonly-cited
15–20% word-of-mouth critical-mass threshold (Rogers' diffusion research,
via a marketing-OER paraphrase FR-20 itself flags for re-verification),
FR-20's own conclusion is explicit: this "does not confirm Prague is dense
enough; it shows the threshold is not obviously out of reach for a market
this size" — weaker than a locality lead position needs.

**Decision: this does not move "Local" to the lead position.** The
estimate is order-of-magnitude, not a count, with its widest uncertainty
in exactly the category (smallest, most numerous productions) that would
matter most for word-of-mouth density — too uncertain to carry a locality
claim as the product's headline. It continues to support only a
distribution angle (H3's Prague-first go-to-market, the film-school free
tier), never the position itself; distribution channel and product
positioning stay different questions, and this draft is about the latter.
What would move it: FR-20's own named follow-ups (a direct read of
`filmcommission.cz/en/statistics/` or `productionlist.com`'s actual date
range landing a real count instead of an estimate), or real interview data
from FR-3 — still blocked on INBOX #1 — including the estimation question
FR-20 proposed adding to that script.

**4. Live and offline-honest: "the call sheet that still works when the
set has no signal."** Chosen. Reasoning below.

## Chosen position

Re-confirmed against FR-20 (2026-09-23, FR-70): the same reasoning standard
applied to alternative 3 above applies here — FR-20's order-of-magnitude,
high-uncertainty estimate is not strong enough evidence to unseat the
chosen position either, so live+offline-honest stands as drafted below,
unrevised.

**"The call sheet that's actually live — and honest the moment it isn't."**

A shoot day's call sheet changes constantly (BRIEF.md's working
hypothesis, Q3's candidate pain list: late revisions, wrong call times).
Every crew member should see the current revision the instant it
publishes, and the app should never lie about whether what's on screen is
current — it says so plainly when it's showing a cached copy instead
(built: FR-9's offline-honest status, FR-16's "REV B replaces A" push and
in-sheet note, FR-11's crew link and QR).

### Why this is not already someone else's position

The dod for this item requires checking whether a competitor already owns
the chosen position, not assuming it's free. One does, partially:

- **StudioBinder already calls its own product a "living" call sheet** —
  the latest revision always loads, with a revision history
  (`competitive-teardown.md`, "Revise" section, citing
  `support.studiobinder.com`). A bare "always up to date" claim collides
  with an incumbent's own marketing language and would read as a copy of
  it, not a distinct claim.
- What StudioBinder has **not** verifiably shipped is the offline half.
  Re-verified directly against StudioBinder's own support article
  (`competitive-teardown.md`, "View offline", FR-138, 2026-10-06,
  headless-rendered, not a third-party snippet): StudioBinder confirms
  **no native iOS/Android app exists**, only a mobile-responsive web view
  for recipients — ruling out the on-device caching a native app would
  need — but the article never uses the word "offline" and does not
  itself confirm or deny genuine offline support either way. The earlier
  "in the pipeline" framing (a third-party review, never vendor-confirmed)
  is superseded by this primary-source read: "not offline-capable today"
  is the defensible claim, not a stated roadmap item. SetHero is
  explicitly designed to assume a signal (browser-only, no app), and
  Yamdu/Croogloo's offline behavior stays unverified either way. Movie
  Magic is offline only as a side effect of distributing a static PDF that
  has none of the "always latest" behavior the others advertise. The
  teardown's own synthesis: "a call sheet that is genuinely both live
  *and* offline-honest... is not something any researched incumbent
  currently and verifiably ships."

So the defensible half of the position is not "live" alone (StudioBinder
already claims that) — it's the conjunction: live when there's signal,
and truthful rather than silently stale when there isn't, verified as a
real product behavior in this repo (FR-9's cached-copy status label with
timestamp, tested against a real build) rather than a marketing adjective.
That re-verification already ran (FR-138, above) and the position stands
on today's evidence — the failure case below names what would still
flip it.

### Supporting proof points (in priority order, all already built)

1. Offline-honest status: the app states plainly when it's showing a
   cached copy and from when, never a silent "live" that's actually stale
   (FR-9).
2. Push notification + in-sheet note on every revision, with delivery
   logged per crew member so an AD can see who did not get REV B (FR-16).
3. One-tap crew link and QR, no app install, no typed IDs (FR-11).
4. Personal call: each crew member's own call time and department surface
   first, not a shared PDF everyone has to search (FR-13).

### Who it's for (per FR-2's Q6 finding)

Every incumbent researched sells to the production office (producer, PM,
line producer), not the AD who assembles the sheet day to day
(`competitive-teardown.md`, Q6 note). This draft's language above is
written for the AD/production-coordinator user, but the buyer question
(Q4: who pays, at what price) is still open and belongs to FR-3, not
assumed here. H3's figure (`BRIEF.md`, a per-production flat fee,
€99–499, unlimited crew) is carried as a hypothesis only, not restated as
a decided price in this document.

## Failure case

FR-2's original **unverified** flag on StudioBinder's offline capability
was re-checked once already (FR-138, 2026-10-06, primary source): no
native app exists, but the vendor's own text still neither confirms nor
denies genuine offline support — the position held. If a future
re-verification (on this narrower remaining question, or on any other
competitor) finds StudioBinder — or any competitor — has since shipped
genuine live-and-offline-honest behavior, this document is wrong and must
be revisited, not defended: re-run the "why this is not already someone
else's position" check above against the new evidence and either sharpen
the distinction (e.g. on the honesty/timestamp behavior specifically, not
offline capability alone) or choose a different alternative from the list
above. Likewise, if FR-3 interviews show ADs
don't relate to "offline-honest" as a stated pain (it wasn't on Q3's
candidate list, which names late revisions, wrong call times, no-signal
locations, missed updates, and printing cost/waste — "no-signal locations"
is the closest match but is about location signal, not app behavior), this
position should be re-tested against whichever of those five pains
interviewees actually rank highest, rather than kept on the strength of
desk research alone.

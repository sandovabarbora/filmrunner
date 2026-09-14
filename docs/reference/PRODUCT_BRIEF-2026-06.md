> Reference only, not a source of truth (see docs/company/TEAM.md). Copied verbatim on 2026-09-14 from the old repository `film_production` (PRODUCT_BRIEF.md, authored 2026-06-11). Its claims are hypotheses for BRIEF.md to test, not conclusions.

# FilmRunner — Product Brief

*Authored 2026-06-11 from founder/mentor strategy session. This document is the
constitution for the rebuild. When a feature idea appears, it must justify
itself against this brief — not the other way around.*

---

## 1. Thesis

**The living call sheet, built for the 1st AD.**

One person drives, forty people consume. The call sheet stops being a
midnight PDF and becomes the production's heartbeat: call times, schedule
slips, "we're on scene 42", who has confirmed. Every call sheet sent is a
product demo delivered to 40 pockets.

The 60-second demo that sells it:

> **"From script to a call sheet in everyone's pocket in 30 minutes."**
> Paste a script → AI drafts the breakdown → drag strips into days →
> publish → the crew's phones light up. Nobody can demo this today —
> not Movie Magic, not StudioBinder, not Yamdu.

## 2. Who

- **Design center (the operator):** the **1st AD**. Every screen is designed
  for their Tuesday. Producers, coordinators, and directors are welcome
  users, but when two design choices conflict, the AD wins.
- **The consumers:** the crew — 10 to 40 people on phones, in parking
  garages, forests, and basements. They never "learn the app"; they tap a
  link and it just works.
- **The buyer:** the producer who approves a line item.
- **Segments:** the data model is universal (a shoot day is a shoot day),
  but marketing, onboarding, and polish target working productions —
  starting with the Czech scene.

## 3. Business model

- **Per production, flat fee** (tiered by production size, e.g. €99–499),
  **unlimited crew**. Matches how film money works: a line item in a budget,
  zero per-seat friction for crew to join.
- **Free for film school productions** (FAMU, Zlín…) — seeding tomorrow's
  ADs and producers.
- 12-month goal: **real paying productions**, even a handful.

## 4. Distribution (the actual product for the next 6 months)

1. **Prague/CZ film scene first** — dense, reachable, talks to itself.
2. **Film schools free** — student productions as the farm system.
3. **Concierge onboarding** — we personally set up the first productions'
   schedules and call sheets. Unscalable on purpose: it's how we learn the
   workflow truth we don't have from the inside.
4. **Direct pilots via existing film contacts** — favors first, invoices later.

## 5. Scope — the full chain, thin everywhere except the shoot day

v1 covers **script → breakdown → schedule → call sheet → shoot day**, under
one iron rule:

> **Every upstream stage earns only enough features to feed the next stage.**
> Script→breakdown is "paste script, AI drafts it, you correct it" — not a
> tagging workbench. Breakdown→schedule is drag-strips-into-days with smart
> warnings — not Movie Magic parity. All product *depth* lives at the end:
> the living call sheet and the shoot-day experience.

### AI's role: invisible glue

AI removes typing, never makes decisions. Paste any script / schedule /
email → structured data. Auto-draft tomorrow's call sheet from today's.
Never branded as "AI" in the tool — it just feels like magic autofill.
The AD always confirms; the system never silently decides.

### Cut from v1

- **Budgeting & cost tracking** — producers keep their spreadsheets. Trust
  in numbers takes years to earn; we don't ask for it yet.

### In scope but sequenced AFTER the first pilot

(These stayed on the roadmap by founder decision, but none may block pilot #1.)

- Breakdown depth beyond cast/locations/key props
- Script revision tracking (colored pages)
- Third-party integrations (beyond email/SMS/push delivery)

**The pilot bar is the 30-minute demo loop, not feature completeness.**

## 6. UX spine

**The shoot-day timeline is home.** A horizontal strip of days
(prep → shoot → wrap); tap a day to enter its schedule and call sheet.
"Day 14 of 32" is the production's heartbeat and the app's first-class
primitive — the thing no horizontal tool (Notion, Monday) can ever own.

```
WED 11        THU 12        FRI 13
┌────────┐  ┌────────┐  ┌────────┐
│ DAY 13 │  │▶DAY 14 │  │ DAY 15 │
│ ✓ shot │  │ sc 42,7│  │ sc 12  │
│ 8/8 sc │  │ CS sent│  │ ⚠ draft│
└────────┘  └────────┘  └────────┘
 today ▲           day 14 of 32
```

Three core screens, in priority order:

1. **Timeline** (home) — the production at a glance.
2. **Day view** (the AD's cockpit) — schedule strips, call sheet status,
   confirmations, publish button.
3. **Crew call sheet** (the consumer surface, PWA) — my call time, my
   location, what changed, works in a forest.

## 7. Brand

- **Name: FilmRunner** (kept — runners keep sets moving).
- **Look: pro tool, daylight-first.** Light, high-contrast, dense-but-calm —
  Linear meets a well-set call sheet. Dark mode for night shoots (Submarine
  Red survives). The Criterion cinephile romance lives on the landing page,
  not inside the tool.

## 8. Architecture

- **Stack:** Next.js + FastAPI + Supabase (kept — salvage the hardened
  backend organs: auth deps, RLS, security work). Condition: **Redis is
  optional in dev**, and no new infrastructure services until a pilot forces
  them. Complexity budget is reserved for offline sync.
- **Crew platform: offline-first PWA.** No app-store install — "tap the link
  in your call sheet message."
- **Offline model: cache + staleness honesty.** Service worker caches the
  crew's day data; every screen shows "last synced 06:12" prominently;
  background sync on reconnect. The crew view is read-mostly, so write
  conflicts barely exist. A call sheet that lies when offline is worse than
  a PDF — staleness is always visible.
- **Live updates: event log + push.** Every change (call time moved, scene
  reordered) is an explicit event → crew sees a change feed
  ("⚠ call moved 7:00 → 7:30") + push notification for critical changes.
  Changes are first-class and auditable, never silent mutations.

## 9. Working process

**Brief → design → vertical slice.**

1. This brief (done).
2. Design the three core screens before product code.
3. Build ONE vertical slice: script in → call sheet on a phone.
   Every iteration demos that loop getting better — never sideways features.

## 10. Guardrails (the anti-Yamdu rules)

1. **One operator.** If a screen isn't for the 1st AD or the crew member,
   it waits.
2. **The chain stays thin.** Building subcategory dropdowns for breakdown
   elements = we died the Yamdu death again. Stop.
3. **Depth at the end.** Polish budget goes to the call sheet and shoot day,
   not to prep tooling.
4. **The pilot bar is the loop.** "Does pilot #1 need this?" is asked of
   every task.
5. **Staleness honesty.** Never present cached data as live. Trust dies on
   the first wrong call time.
6. **Changes are events.** A silently updated call time is a missed call
   time.
7. **Distribution is product.** Half the founder's time goes to Prague film
   people, not code.

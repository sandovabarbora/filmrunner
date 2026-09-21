# Pilot outreach message

FR-41. Role: marketing. Date: 2026-09-21. Tone and claim from
`docs/marketing/positioning.md` (FR-6): "the call sheet that's actually
live — and honest the moment it isn't." Grounded in what
`docs/research/pilot-readiness-2026-09.md` marks PASS on the live stack;
anything it marks NOT VERIFIED is left out of the promise below, per this
item's own failure case.

## Status of this draft

This is text for the founder to send from her own name and number/e-mail —
sending it is gated (see `docs/company/INBOX.md` #1: the routine has no
access to the founder's network and must not contact anyone but her). Real
recruiting for FR-3's five interviews still waits on that same approval.
This message is a separate ask (one pilot shoot day, not a 30-minute
interview) but should go out through the same channel once the founder
picks candidates, so both can be sent together if that is simpler for her.

## WhatsApp message (Czech)

> Ahoj [jméno], píšu ti ohledně natáčecího listu (call sheetu) —
> zkoušíme FilmRunner, appku, co ho drží živý a na telefonu funguje i bez
> signálu (a poctivě řekne, když zobrazuje starší uloženou verzi, ne že to
> tváří jako aktuální). Ukázka je tady: [ODKAZ NA LANDING]. Hledám jeden
> natáčecí den na reálné produkci, kde bych to nasadila naostro a byla u
> toho, kdyby něco. Nic se neinstaluje, nikdo se nikam nepřihlašuje —
> stačí odkaz na telefonu. Máš chvilku probrat, jestli by se to hodilo na
> něco, co teď točíte?

WhatsApp length: under 500 characters, no feature list, one link, one ask.

## E-mail version

### Czech

Subject: Jeden natáčecí den na vyzkoušení call sheetu, co nelže o tom, jestli je live

> Ahoj [jméno],
>
> dělám FilmRunner — call sheet, který je opravdu živý (každá revize se
> objeví u štábu hned) a zároveň poctivý: když telefon nemá signál,
> aplikace to řekne a ukáže poslední uloženou verzi s časem, kdy se
> stáhla, místo aby dělala, že je vše aktuální.
>
> Ukázka (bez přihlašování): [ODKAZ NA LANDING]
> Živá appka: [ODKAZ NA DEMO]
>
> Hledám jednu produkci a jeden natáčecí den, kde bych to nasadila naostro
> — publikuju s vámi call sheet, sleduju, jestli štábu dorazí, a beru
> zpětnou vazbu přímo od vás a od 1. AD. Žádný závazek na víc, žádná
> platba, žádný účet, který by po natáčení zůstal viset.
>
> Máš chvilku příští týden na krátký hovor?
>
> [jméno]

### English (below the Czech)

Subject: One shoot day to try a call sheet that's honest about being offline

> Hi [name],
>
> I'm building FilmRunner — a call sheet that's genuinely live (every
> revision reaches the crew immediately) and honest about it: when a phone
> has no signal, the app says so and shows the last saved copy with a
> timestamp, instead of pretending it's current.
>
> Demo (no sign-in): [LANDING LINK]
> Live app: [DEMO LINK]
>
> I'm looking for one production and one shoot day to run this for real —
> publish the call sheet with you, see whether it reaches the crew, and
> get feedback straight from you and the 1st AD. No ongoing commitment, no
> payment, no account left dangling after the shoot.
>
> Got a few minutes for a quick call next week?
>
> [name]

Both versions link the same two pages: the landing page
(`https://sandovabarbora.github.io/filmrunner/landing.html`, FR-25) and the
live demo (`https://sandovabarbora.github.io/filmrunner/`, the two-doors
entry page). Neither message lists more than the one claim above — no
three-bullet feature list, per the dod.

## What to say when they ask about offline / data / price

Honest answers only, each grounded in what
`docs/research/pilot-readiness-2026-09.md` actually shows as PASS today,
not in what the product is meant to do eventually.

**"Does it really work with no signal?"**
Verified on a real build: once a crew member has opened their link with
signal at least once, the app shows the cached call sheet and says plainly
it's a cached copy with the time it was saved, rather than claiming it's
live (FR-9, "Offline reload is honest" — PASS in the desktop/headless
check; the on-phone airplane-mode check is still on the founder's list,
readiness file row 18, NOT VERIFIED yet). Say: "it's been tested to fail
honestly, not silently — the actual on-set airplane-mode check is next on
our list, and your pilot day would be part of proving it."

**"What happens to our data?"**
Say only what is true today: data lives in one Postgres database
(Supabase, Frankfurt), nothing is public unless it's a crew member's own
personal link or the crew/production sheet link the AD shares, and nothing
is sold or shared with anyone else. Do not promise a written data-processing
agreement, GDPR paperwork, or a retention policy — none exists yet
(`docs/company/INBOX.md` has no item for this; if asked for a written
policy, say it's being drafted and follow up rather than improvising terms
live).

**"Can crew reply or ask questions in the app?"**
No — say so directly. The crew's own channel today is WhatsApp: the AD can
send the day as a WhatsApp message and each crew member their own
personal-call WhatsApp link (FR-29), but the app itself has no chat or
comment feature.

**"What does it cost?"**
Say it's free for the pilot, full stop — no price has been set or tested
yet (`BRIEF.md` H3's €99–499 figure is an unverified hypothesis carried
from a prior document, not a quote; do not repeat that number to a
candidate). If pressed: "we're not charging for this pilot — the point is
to learn whether it's useful before we think about price at all."

**"Do we need to install anything or make an account?"**
No install, no account for crew — a link opens the sheet, and adding it to
the home screen is optional (readiness file, "For the founder's phone,"
step 2). The AD/production coordinator signs in with an e-mail code to
edit — say plainly that this sign-in step is being finished this week
(INBOX #3) and confirm it's working before promising a pilot date depends
on it.

**"Will everyone get notified automatically?"**
Say it's built (Web Push, FR-16) but not yet confirmed working end-to-end
on a real iPhone (readiness file rows 20-21, NOT VERIFIED — needs the
founder's phone). Offer the honest fallback that is verified: "REV B
replaces A" also shows in the app itself and can be sent as a WhatsApp
message with one tap, so nobody is silently missed even before push is
confirmed on a real phone.

## Failure case

Before sending either version, check this file's claims against the
current state of `docs/research/pilot-readiness-2026-09.md`: anything that
file marks NOT VERIFIED must not appear as a promise above without the
matching caveat, and anything it later marks FAIL must be removed from
both message drafts and the Q&A block in the same edit that records the
failure, not left standing on the strength of an earlier pass.

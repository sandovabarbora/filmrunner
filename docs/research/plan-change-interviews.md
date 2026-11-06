# Plan-change interviews: deciding, replanning or telling

FR-208. Role: pm. Date: 2026-11-05. Runs alongside the FR-3 script in
`discovery-plan.md`; for the conversations below, use this one.

## The question

Outreach to production companies named a sudden plan change as the biggest
pain. "Plan change" hides at least four different jobs:

| Phase | What it is | Does FilmRunner help today? |
|---|---|---|
| **Deciding** | What do we do now, and what does each option cost? | No, deliberately |
| **Replanning** | Who and what is still free: actors, kit, location, permit, catering | Only moving a scene or a day; it does not check availability |
| **Telling** | Everyone knows the new plan, and we know that they know | Yes, this is what FR-200 to FR-207 built |
| **Paying** | What the change cost afterwards, who absorbs it | No |

If the pain is Telling, the product is on target and the next step is a pilot.
If it is Deciding or Replanning, the same outreach sentence is true and the
product solves the smaller half. This guide exists to tell these apart.

## Why the FR-3 script cannot answer this

- It asks about call sheets, so every answer is about call sheets.
- Its Q3 prompt list names late revisions and a crew member missing an update,
  so the Telling answer is suggested before it is earned.
- The BRIEF kill criterion counts "unprompted or confirmed", so a prompted
  yes passes it. Record unprompted answers separately.
- Its target roles leave out producers and heads of production, who are the
  people outreach actually reached and who would pay.

## Who to talk to

Five to six conversations, starting with whoever replied to the outreach.

| Slot | Role | Why |
|---|---|---|
| 2 | Producent, vedoucí produkce | They decide and pay. Expect them to lean towards Deciding and Paying |
| 2 | 1st AD, vedoucí natáčení, produkční | They replan and tell. Expect them to lean towards Telling |
| 1 | Head of department or a vendor | They are on the receiving end |
| 1 (best) | Second person from a production already in the sample, about the same incident | Shows whether the two roles remember the same night differently |

Role shapes the answer, so never add answers across roles without showing the
split. A split is itself a finding: if the buyer's pain differs from the user's,
that is a sales problem as well as a product one.

## Rules for the interviewer

- Past events only. A story about last Tuesday outweighs any opinion about
  what would be useful.
- Do not use the words decide, inform or communicate until they do. Let them
  name the hard part.
- No product until section 5. People who have heard a pitch are polite.
- Compliments and "that would be great" are not evidence. Time spent, money
  spent, things they already tried and a date offered for a pilot are.
- If they generalise ("it's always chaos"), bring them back: "A tehdy, v tu
  konkrétní noc?"
- Silence is a tool. Leave it three seconds longer than feels comfortable.

## The 30-minute script

The questions use formal Czech for cold contacts; switch to *ty* when you know
the person and adjust gender endings.

### 0. Opening (2 min)

> Děkuju, že jste si našli čas. Nebudu vám nic prodávat, zajímá mě, jak to u vás
> doopravdy probíhá. Můžu si dělat poznámky? Bez vašeho souhlasu nikde neuvedu
> jméno vaše ani produkce.

If they replied to the outreach, quote their own words: "Psali jste, že
[jejich formulace]. Chtěla bych tomu rozumět na konkrétním případu."

### 1. Context (2 min)

> Na čem jste pracovali naposledy, jak velký byl štáb a jaká tam byla vaše role?

Note the size bucket from `discovery-plan.md`.

### 2. The last change, by the clock (15 min)

This is the interview. Draw a timeline on paper and fill in clock times as they
talk.

> Vzpomeňte si na poslední natáčení, kdy se plán změnil na poslední chvíli. Co se
> stalo?

Let them tell it through once, then walk back along the line:

- Kdy a od koho jste se to dozvěděli?
- Co jste udělali jako první?
- Co bylo potřeba zjistit, než bylo jasno, co dál? Kde jste to zjišťovali?
- Kdo nakonec řekl, jak to bude? Jak dlouho to trvalo?
- Co všechno se kvůli tomu muselo přeskládat nebo přeobjednat?
- Komu bylo potřeba dát vědět? Jak jste to udělali?
- Podle čeho jste poznali, že to všichni vědí?
- Dozvěděl se to někdo pozdě nebo špatně? Co se pak stalo?
- Kolik to celé stálo: čas, peníze, nervy? Kdo to nesl?
- V kolik jste to měli hotové a v kolik jste šli spát?

General probes: "Co bylo dál?", "Jak to myslíte?", "Proč to bylo důležité?"

### 3. The worst one (5 min)

> Který případ si pamatujete jako nejhorší? Co se tehdy pokazilo?

Only find the moment it went wrong and what it caused. The point is to learn
whether the worst case broke in the same phase as the ordinary one.

### 4. Where it really hurts (3 min)

Ask in this order. Each is harder to answer politely than the one before.

1. > Co jste zkusili, aby se to příště neopakovalo? Platili jste za něco?
2. > Kdybyste tu noc měli na dvě hodiny někoho navíc, co byste mu dali dělat?
   > A co byste mu nesvěřili?
3. > Co z toho, co jste popsali, byste už nikdy nechtěli dělat?

Question 2 is a hypothetical on purpose. It forces a choice, and the part they
would not hand over shows where their own judgement is needed.

### 5. The product, and its own test (2 min)

Show only the screen of one person's changed sheet and the AD's confirmation
list. Then go back to their timeline, not to the screen:

> Co tady vidíte? Změnilo by to něco na té noci, o které jste mluvili? Kde,
> jestli vůbec?

"Nothing, the problem was elsewhere" is a useful answer. Thank them for it.

### Close (1 min)

> Točíte v příštích čtyřech týdnech něco, kde bychom to mohli zkusit, se mnou
> na telefonu? A s kým dalším bych si o tom měla promluvit?

A date is evidence and a "maybe, get in touch" is not. Ask only once the live
stack works (Supabase restored, sign-in checked, FR-200 to FR-207 deployed).

## Notes template

One file per interview, named `<yyyy-mm-dd>-<role>-<size-bucket>.md`. Keep these files outside this repository: they hold people and companies, and the repository is public. Only the anonymised conclusion goes in `DECISIONS.md`.
Fill the table the same day; the "evidence" lines are quotes or numbers, not
impressions.

```
# Interview: <role> · <size bucket> · <yyyy-mm-dd>

Source channel: outreach reply | founder network | referral
Consent to quote by name: yes/no
Their own words from the outreach reply:

## Incident 1 (last change)
Trigger: weather | person | location | money | other
Learned at: ... Everything settled at: ...

| Phase | From-to | Who | Tools | What went wrong | Consequence |
|---|---|---|---|---|---|
| Deciding | | | | | |
| Replanning | | | | | |
| Telling | | | | | |
| Paying | | | | | |

Who was late or wrong, and what it caused:

## Incident 2 (worst)
Phase where it broke:
Consequence:

## Section 4
Already tried or paid for:
Two extra hours would go to:
Would not hand over:
Never again:

## Section 5
What they said would change on that night, in their words:
Pilot: date offered | maybe | no

## My coding (not their words)
Heaviest phase, incident 1:
Phase where it broke, incident 2:
Named first, unprompted:
```

## How to read the result

Write down your prediction before the first conversation, and agree these rules
before it too: changing them afterwards means they no longer test anything.

Five or six conversations give a direction, not a measurement. The thresholds
are a starting proposal and have no source behind them.

An incident counts for a phase when the phase took the most time **or** the
real consequence came from it. An incident can count for two phases.

| What you see | What it means | Next step |
|---|---|---|
| Telling in at least half of incidents, and at least one operator and one buyer | The product is on target | Deploy, offer pilots, measure with `docs/pilot/pilot-plan.md` |
| Replanning leads, and the time goes on checking who and what is free | The product comes one step too late | Shape "what does this change touch" before publishing; no new feature until a second round agrees |
| Deciding or Paying leads | The product does not solve the named pain | Stop feature work and re-frame in `BRIEF.md`: this is the buyer's problem, and Telling is at most a side benefit |
| Operators say Telling, buyers say Deciding or Paying | Real pain for the user, none for the payer | Test who pays before building further, using the Q4 ladder in `discovery-plan.md` |
| No pattern | Too few conversations, or several different problems | Three more, in whichever role is thinnest |

Strongest single signal, whichever row applies: they already tried something or
paid for something for this phase, or they offered a pilot date.

## Outreach follow-up

For people who replied. Not yet sent; it goes out from the founder, under
`docs/company/INBOX.md` #1.

> Dobrý den, [jméno],
>
> psali jste mi, že [jejich formulace]. Moc to pomohlo, díky. Rozumím tomu ale
> zatím jen obecně a ráda bych to pochopila na jednom konkrétním případu.
>
> Mohli bychom si na 30 minut zavolat o tom, kdy se vám naposledy změnil plán na
> poslední chvíli? Nebudu nic prodávat. Přizpůsobím se vašemu času, klidně i
> večer nebo mezi natáčením.
>
> [jméno]

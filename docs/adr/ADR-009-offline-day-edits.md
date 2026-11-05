# ADR-009: Day-schedule offline edits stay read-only; no queue

Status: accepted (recommendation b — keep current behavior)
Date: 2026-10-15. Serves FR-175. Answers the gap FR-147 (2026-10-07) found
and explicitly left undecided.

## Context

`frontend/src/editor/screens/DayEditor.tsx:75` sets
`readOnly = offline || !canPublish`. While offline, every field on the
day's schedule — calls, scenes, personal calls, cast calls, safety notes
— is disabled, and the publish panel shows "Read-only while offline.
Reconnect to publish." A draft the AD typed is kept on the phone
(`drafts.ts`, autosaved on every change and flushed on `pagehide`), so
nothing is lost; the AD just cannot publish until back in signal.

`frontend/src/editor/crewEdits.ts` (FR-18, extended FR-144) already solves
a structurally similar-looking problem for crew contact fields: an edit
made offline is queued in IndexedDB and retried later, not blocked. Its
own doc comment names the one reconciliation rule it had to get right:
only the fields actually changed (`diffCrewEditFields`) are stored and
sent as a partial patch (`exclude_unset` merge), so a second device's
sync of its own unrelated field edits can't silently revert the first
device's change to a different field.

Nothing in this repo had compared the two paths and decided whether the
day schedule should get the same treatment. This ADR does that, against
exactly these two precedents — no third option is invented.

## The reconciliation question a day-schedule queue would raise that crew edits don't

`crewEdits.ts` patches one existing crew member's own contact record
(name, phone, department, position, standard call time, HoD flag) — flat,
independent scalar fields that nobody else is watching in real time. If
two devices queue edits to *different* fields of the same member and sync
in either order, the partial-patch merge is correct by construction: each
sync only touches the keys it actually changed.

Publishing a day is not a patch to one record's fields; it is
`revisionPayload()` building one complete, atomic snapshot of the whole
day — schedule items (an ordered array), crew calls and cast calls (maps
keyed by person) — and the server (`publish_revision`,
`backend/app/services/call_sheets.py:90`) replacing "current" with that
whole snapshot as a new immutable revision, serialized by an advisory
lock so two near-simultaneous publishes from the *same* device never race.
There is no field-level patch on the wire today, and no server-side merge
of two revisions at all — the second publish simply becomes the new
current revision, full stop.

So the concrete question a queue would force is: **when two devices each
queue a full-snapshot publish for the same day while both are offline,
and reconnect in either order, what happens to the one that syncs
second?** Unlike the crew-edit case, there is no existing diff machinery
to merge "device A changed the crew call time" with "device B reordered
scene 4" into one correct result — a full snapshot has no notion of
which of its fields the human actually intended to change versus which
were just carried over unedited from whatever revision that device last
saw. Replaying it as-is would silently clobber whatever the other device
published, including changes the first device never saw and the second
device's user never intended to touch.

This matters more here than for a crew member's own contact details
because of who is reading the result: the moment a revision is current,
every crew member's personal link treats it as "today's truth" — the
call time they wake up for, the location they drive to, the safety
notes for the day. A silently wrong merge on this document reaches
dozens of people instantly and without review; a stale field in one
crew member's own contact row reaches nobody but that lookup.

## Decision

**(b) Keep the current explicit "read-only, reconnect to publish"
behavior.** Do not build a day-schedule offline-edit queue now.

Reasoning:

- The publish payload is a whole-document snapshot, not field-level
  patches. Queuing-and-replaying it offline would need either (a) real
  merge logic for an ordered array (`schedule_items`) and two
  person-keyed maps (`crew_calls`, `cast_calls`) — substantially more
  surface area than `crewEdits.ts`'s flat scalar record — or (b) conflict
  detection (reject a stale-base publish and ask a human to look again),
  which is just today's "reconnect and look at the live state before
  publishing" behavior with extra steps and a false sense that the edit
  already "took."
- What gets published is what every crew member's personal link trusts
  immediately as today's truth. Today's explicit block is honest: an AD
  who is offline cannot have silently changed what the crew sees, because
  nothing crew-facing changes until a human, back online, looks at the
  current revision and chooses to publish. A queue that replays
  automatically risks two different crew members ending up having seen
  two different "final" versions of the same day, with no one AD aware
  a merge even happened.
- The role that can publish (`canPublish`) is narrow — the person running
  the day — and the measured cost of staying read-only is low: the draft
  is never lost (autosaved locally, kept across reconnects), only
  delayed until signal returns. There is no FR or interview evidence of
  the same day being edited from two devices while both are offline
  often enough to be a real pain point; this is a hypothetical risk
  today, which is itself part of why a safer, dumber behavior should win.

Moving a scene, moving a day and swapping two days (FR-203, `app/services/replan.py`) follow the same rule: each publishes a revision, the controls are hidden while `readOnly`, and nothing is queued offline.

## Failure case / when this would be the wrong call

If the current behavior is wrong, it is wrong because a partially-synced
day schedule risks showing different crew members different versions of
"today's truth" without anyone noticing — which is the current ADR's own
reason for choosing (b), restated as a risk rather than a reassurance.
Stating it plainly rather than defaulting to "build the queue because a
working pattern exists elsewhere": the existence of `crewEdits.ts` is not
evidence this case needs the same treatment, because the two documents
being edited have different blast radii once synced.

## Revisit when

- Real usage shows the same unpublished day edited from two devices while
  both are offline often enough to cause lost or clobbered edits (not a
  hypothetical — an actual pilot incident or a crew/AD report), **or**
- The publish payload itself moves from a full-snapshot revision to
  field-level patches (closer to how `crew_calls`/`cast_calls` already
  look) — at that point a queue could reuse `crewEdits.ts`'s
  diff-then-partial-patch pattern per field instead of per whole
  document, and this decision should be revisited with that design in
  hand, not before.

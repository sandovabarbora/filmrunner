# Data retention (FR-74)

What happens to a production's data over time, and what actually happens
today when a crew member is removed — checked against the code on
2026-09-23, not assumed. This is a policy proposal plus an honest account
of current behaviour, some of which does not yet match `privacy.html`'s
claims (fixed in this same PR) or match the policy proposed below (left
as proposed text, per this item's own failure case: nothing here deletes
real data).

## What removing a crew member does today (verified against the code)

`DELETE /productions/{id}/crew-members/{member_id}` (`app/routers/productions.py:414`)
deletes the `crew_members` row. Verified live against a local Postgres
(`backend/alembic/versions/*` migrations, models in `app/models/`):

- **Deleted with it** (`ondelete="CASCADE"` on the foreign key, confirmed by
  actually deleting a member with both rows present and re-querying):
  the crew member's `CrewCallEntry` rows (personal call times per
  revision, FR-24) and `RevisionView` rows (read receipts, FR-36).
  `privacy.html`'s claim that removal "drops your personal times [and]
  open records" is correct.
- **Deleted with it, fixed 2026-09-24 (FR-79)**: if the crew member has an
  active `PushSubscription` (FR-16), it is dropped along with them.
  `push_subscriptions.crew_member_id` originally had a plain foreign key
  with no `ON DELETE` clause (`alembic/versions/c2a1f9e7b3d4_push_subscriptions.py:31`),
  so Postgres raised `ForeignKeyViolation` and the whole removal was
  rejected — reproduced directly against a local database on 2026-09-23.
  Migration `d8f4b1c9a2e6` (FR-79) added `ON DELETE CASCADE`; a crew
  member with an active push subscription has succeeded, not 500'd, on
  removal since that merge — reconfirmed live 2026-10-19 (FR-184) and
  covered by a regression test
  (`backend/tests/test_push.py::TestRemovalWithActiveSubscription`).
  `privacy.html`'s "removal also drops... your push odběr" is correct.
- **Kept, not deleted, and not claimed to be deleted**: the shared
  `Contact` row (name, phone, e-mail, photo) survives crew-member removal
  — confirmed live (delete a crew member, the `contacts` row is still
  there). `Contact` is deliberately shared across crew/cast (see the
  model's own docstring in `app/models/production.py`), so nothing
  currently deletes it when the last crew/cast membership pointing at it
  is removed; it becomes an orphaned row with no cleanup path. Not a
  contradiction of anything `privacy.html` currently states (it does not
  claim contact details are dropped on removal), but worth naming here
  since the person's name/phone/photo persists indefinitely once
  orphaned.

## What "deletes the production" means today: nothing yet

`privacy.html` (before this PR) said data stays "until the production
removes you from the crew or deletes the production." There is no way to
delete a production today: no `DELETE /productions/{id}` endpoint exists
(`app/routers/productions.py` has deletes for members, locations, cast
members and crew members, never for a production itself) and
`backend/scripts/production_backup.py` only exports/imports, never
deletes. `privacy.html` is corrected in this PR to say data stays "until
the production removes you from the crew; there is no way yet to delete
a whole production" rather than promising a control that does not exist.

## Proposed policy (not yet implemented — text only)

Propose **12 months** after a production is marked `wrapped` as the
retention window for a wrapped production's contacts, photos, push
subscriptions and read receipts, after which they would be deleted
automatically. Reasoning: a pilot production's crew data has no ongoing
use once the shoot is over and any post-wrap paperwork (deliverables,
insurance claims) is settled; twelve months covers a plausible dispute or
re-hire window (the same production returning for reshoots) without
holding personal data indefinitely, and matches the general norm cited in
GDPR guidance of keeping personal data no longer than the purpose
requires. This is a proposal for the founder to approve, not a decision —
see the failure case below.

**This cannot actually be computed automatically yet**, which the dry-run
script below makes visible rather than faking: `Production` (`app/models/production.py`)
has a `status` enum (`prep` / `shooting` / `wrapped`) and a `created_at`,
but no timestamp for *when* the status changed to `wrapped`. A production
created in January and wrapped in November looks identical, from the
database alone, to one created and wrapped the same week. Implementing
the 12-month policy for real would need a `status_changed_at` (or a
dedicated `wrapped_at`) column, set when a production's status transitions
to `wrapped` — not built in this item, named here as the concrete
prerequisite for whoever picks up automatic deletion.

## Dry-run report

`backend/scripts/retention_report.py` — read-only, no deletion, no
account needed. Lists, against the real database:

- every `wrapped` production, its `created_at` age (labelled as a proxy,
  not time-since-wrap, per the gap above), and counts of its contacts,
  crew members, push subscriptions and revision views that the proposed
  policy would eventually delete
- crew members with an active push subscription, as plain informational
  context (removal cascades their subscription cleanly since FR-79,
  shipped 2026-09-24)
- contacts orphaned (no crew or cast membership on any production) as of
  today, which nothing currently cleans up

Run it with `cd backend && python -m scripts.retention_report`.

## Failure case

This item proposes a policy and reports what it would affect; it does
not implement deletion. Automatic deletion — even of data this document
recommends removing — stays proposed text until the founder approves it
via a new `INBOX.md` item, so nothing in this PR can delete real pilot
data. FR-79 (the push-subscription cascade fix) is a bug fix that lets an
*existing, requested* removal succeed; it is not the automatic-deletion
mechanism this section proposes, and is filed separately for that reason.

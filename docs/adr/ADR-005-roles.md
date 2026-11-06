# ADR-005: Roles and permissions per production

Date: 2026-09-14. Status: accepted (founder decision in session). Serves
FR-15; founder asked for "PBAC, least privilege".

## Context

After FR-12 any signed-in user could read and change every production.
On set, the 1st AD publishes, a coordinator edits, a producer reads, a
crew member sees only their own sheet (FR-13).

## Decision

- **Membership is per production, invited by email.** A row in
  `production_members` (`email`, `user_id`, `role`) is created by an owner;
  the Supabase user id is bound on the invitee's first authenticated
  request (email match, case-insensitive), so people can be invited before
  they ever sign in. Whoever creates a production becomes its owner.
- **Roles map to explicit permissions**, not to endpoint names:
  `owner` → `production:read`, `production:manage_members`,
  `production:edit`, `day:publish`, `crew:edit`; `editor` → all but
  `manage_members`; `viewer` → `read`. `production:edit` (a production's
  name and lifecycle status) was added to both `owner` and `editor` by
  FR-34 (2026-09-21), a week after this ADR was written; this list is
  kept matching `app/authz.py`'s `ROLE_PERMISSIONS` directly, not restated
  from memory.
  Every production-scoped endpoint declares the one permission it needs
  (`Depends(require("day:publish"))`, or `require_on` when the path carries
  a call-sheet id). Adding a role or a permission touches one table in
  `app/authz.py`.
- **Least privilege by default.** Non-members get 403 naming only the
  production they already asked for; the production list shows members'
  productions only. A production keeps at least one owner (409 on removing
  the last). The service token is owner everywhere and exists for seeding
  and the founder's admin gesture only.
- **The editor reads its rights from the API** (`my_role`, `permissions` on
  each production) and hides what the role cannot do: Members tab for
  owners, New day and publish for editors and owners, read-only day for
  viewers. The API is the enforcement; the UI is a courtesy.
- **Public reads stay public.** The crew link needs no account (FR-13 adds
  the personal variant).

## Out of scope

Per-department permissions for heads of department (needs department
notes to exist first), audit log of role changes, SSO groups.

## Consequences

- Existing productions created before this ADR have no members; an owner
  is added with the service token once after deploy.
- `POST /contacts` is not production-scoped (address book rows); any
  signed-in user can create a contact. `PATCH /contacts/{id}` is guarded:
  the caller needs `crew:edit` on every production that has the person in
  its crew or cast (a contact used nowhere is editable only by the service
  token). Found by the automated commit review on 2026-09-14 as an IDOR;
  tightened from "any production" to "every production" by FR-220, because
  a change shows on all of their live sheets.
- Attaching a contact (`POST .../crew-members`, `.../cast-members`) needs
  the contact to be on a production the caller can see, or on none at all
  (the picker's create-then-attach). Anything else is the same 404 as an
  unknown id (FR-213, FR-220): the attach response carries the person's
  phone and email, and contact ids are public in photo URLs.
- Consequence of the two rules together: an editor who is only a viewer on
  another production using the same person can reuse them, but cannot
  correct their phone, and reusing a person on a new production makes them
  read-only for anyone who cannot edit that new production. The editor
  does not send a contact edit unless the name or phone really changed, so
  role edits and picking someone unchanged are never blocked by this.

## Revisit when

A production needs department-level editing, or a customer needs SSO
group mapping instead of email invites.

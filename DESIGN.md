# FilmRunner — Call Sheet Module: Data Model

Scope note: this skeleton implements only the call-sheet slice of FilmRunner
(not full production management — no budgeting, no scripts/breakdowns, no
scheduling optimizer). The goal is one thing done well: creating, revising,
and distributing shoot-day call sheets, viewable offline on set.

## Why the shape is what it is (industry context, not invented)

Film call sheets follow conventions that are decades old and load-bearing —
getting them wrong makes the tool unusable for an AD (Assistant Director):

- **Same-day revisions are the norm, not the exception.** A call sheet issued
  the night before routinely gets revised the morning of (weather, cast
  availability, location change). Industry convention names revisions by
  color (pink, blue, yellow...) or letter (A, B, C). Modeling `CallSheet` as
  a container with ordered `CallSheetRevision` children — instead of one
  mutable row — is what makes "what changed since the version I printed"
  answerable.
- **Page count is measured in eighths of a page**, not scenes or minutes
  (e.g. "2 3/8 pgs"), because scripts are timed that way industry-wide.
  Stored as `page_count_eighths: int` (an eighth-count, so 2 3/8 pages = 19)
  to avoid float rounding on a number ADs do arithmetic on by hand.
- **Cast status codes are standardized**: W (working), SW (start work), WF
  (work finish), H (hold), SWF (start and finish), R (rehearsal). Stored as
  a constrained enum rather than free text so the generated sheet renders
  the correct code.
- **Offline is not a nice-to-have.** Call times are 5-6am, locations are
  frequently outside cell coverage (rural sets, soundstage basements,
  parking structures), and the call sheet is the one document everyone on a
  50-200 person crew needs before they leave home. Hence the PWA caches the
  last-synced revision in IndexedDB and renders from cache when the network
  fetch fails.

## Entities

**Production** — id, name, working_title, production_company, status
(prep / shooting / wrapped), created_at.

**Location** — id, production_id (FK), name, address, parking_notes,
nearest_hospital, geo_lat, geo_lng.

**Contact** — id, name, phone, email. Shared address-book row referenced by
crew and cast, so a phone-number correction doesn't require touching every
call sheet that mentions the person.

**CrewMember** — id, production_id (FK), contact_id (FK), department,
position, standard_call_time.

**CastMember** — id, production_id (FK), contact_id (FK), character_name,
standard_pickup_time.

**CallSheet** — id, production_id (FK), shoot_date, day_number (e.g. "12"),
day_count (e.g. "30" — for "Day 12 of 30"), unit_name (Main Unit / Second
Unit), status (draft / published / superseded), created_at.
One `CallSheet` per unit per shoot day; it is a container, not itself
versioned — the content lives in revisions.

**CallSheetRevision** — id, call_sheet_id (FK), revision_letter (A, B, C...),
general_crew_call, shooting_call, sunrise, sunset, weather_forecast,
safety_notes, is_current (bool), created_at, created_by.
Immutable once created — a correction creates revision B, it never edits A.

**ScheduleItem** — id, revision_id (FK), order_index, scene_number,
int_ext (INT/EXT), day_night (DAY/NIGHT), set_description, location_id (FK),
page_count_eighths (int), cast_status (list of {cast_member_id, status_code}).

**CastCallEntry** — id, revision_id (FK), cast_member_id (FK), status_code
(W/SW/WF/SWF/H/R), pickup_time, call_time, makeup_hair_time, on_set_time.

**DistributionLog** — id, revision_id (FK), contact_id (FK), channel
(email/sms/link), sent_at, viewed_at (nullable). Lets an AD answer "who
hasn't opened today's revision yet" — a real on-set question at 5am.

## Deliberately out of scope for this skeleton

- Auth/SSO/SAML, Stripe billing, Twilio SMS sending, Resend email sending,
  Frame.io integration — all named in the original full-platform spec, none
  built here. The skeleton uses a stub bearer-token auth and logs
  distribution events without actually sending anything, so the data model
  is provably right before wiring paid third-party services into it.
- PDF export / print-perfect layout beyond a basic print stylesheet.
- Multi-tenant org/permissions model (single production per deployment, for now).

## References

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0 ORM: https://docs.sqlalchemy.org/en/20/orm/
- Alembic migrations: https://alembic.sqlalchemy.org/en/latest/
- Service Worker API (offline caching): https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API
- Web app manifest (PWA installability): https://developer.mozilla.org/en-US/docs/Web/Manifest

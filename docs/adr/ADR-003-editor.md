# ADR-003: The AD editor

Date: 2026-09-14. Status: accepted, corrected 2026-10-20 (FR-192 — Scope
v1, the Connect-screen access decision, the router decision and the
"Revisit when" triggers were stale against the current code; see the
inline updates below). Serves FR-10; BRIEF Q1 (who assembles the sheet)
and Q7 (smallest thing that proves the wedge).

## Context

The crew side works: a link opens a call sheet on a phone, offline, with
hot revisions. The AD side is curl. The editor is the first screen an AD
touches, on set, on a phone, often at 05:30 with a weather change.

## Decisions

1. **Scope v1**: production (pick or create), shoot day (date, day X of Y,
   unit), revision fields (crew call, shooting call, sunrise, sunset,
   weather, safety notes), schedule items (scene, INT/EXT, DAY/NIGHT, set,
   pages in eighths) with reorder and delete. No cast calls, no contacts
   (FR-14), no locations. **Update, FR-192 (2026-10-20): all three shipped**
   — cast calls (FR-33, `castCalls` in `drafts.ts`), contacts (FR-14), and
   locations (FR-17, with delete added by FR-38) are each a tab in
   `route.ts`'s production screen today. This "Scope v1" line describes the
   editor's first cut, not its current scope; see Decision 4 below for what
   it actually covers now.
2. **Draft lives on the phone, the server sees only publishes.** The draft
   is stored in IndexedDB (store `drafts`, keyed by a local id) on every
   change. Publish creates an immutable revision through the existing API:
   the first publish creates the call sheet (revision A), later publishes
   add B, C, ... via `POST /call-sheets/{id}/revisions`. There are no draft
   endpoints; the API stays as it is. **Re-checked, FR-192 (2026-10-20):
   still accurate** — `drafts.ts`'s `Draft`/`loadDraft`/`saveDraft` match
   this description exactly, no drift found.
3. **Access until FR-12**: a Connect screen takes the API base and the
   bearer token once and keeps them in `localStorage`. Marked temporary in
   the UI; FR-12 replaces it with Supabase Auth. **Update, FR-192
   (2026-10-20): FR-12 shipped (2026-09-14) and the prediction in Decision 4
   below ("Connect screen goes away") did not come true — Connect narrowed
   instead of disappearing.** Confirmed directly against
   `frontend/src/editor/EditorApp.tsx:71-73`: a Supabase Auth session
   (`session.ts`, email code or magic link via `<SignIn>`) is the real
   primary access path whenever `signInConfigured` is true, cross-checked
   against `ADR-004-auth.md` (corrected on the same drift this week by
   FR-190). The `<Connect>` screen (API base + bearer token) survives in
   exactly two places, both in `EditorApp.tsx`: the hidden five-tap-on-logo
   admin gesture (`adminScreen`, line 62-69, service-token entry with no
   normal-user UI path to it), and the fallback shown when
   `signInConfigured` is false (line 71-73). No code path was found where a
   signed-in-configured normal user is routed to Connect — the regression
   named in this item's own failure case was checked for and not found.
4. **Where it lives**: a second Vite entry, `editor.html`, in the same
   project and design system. The crew viewer bundle stays free of editor
   code. No router; the editor is one scrolling page with sections.
   **Update, FR-192 (2026-10-20): the "no router, one scrolling page" half
   is stale.** `frontend/src/editor/route.ts` is a real hash router
   (`#/`, `#/p/<productionId>`, `#/p/<productionId>/day/<callSheetId|new>`)
   driving a multi-screen app: a productions list, then a production's
   `days` / `crew` / `cast` / `locations` / `members` / `settings` tabs, and
   a separate day editor screen — the shape FR-14/FR-17/FR-33/FR-38 each
   grew past Decision 1's original "Scope v1". The first sentence (second
   Vite entry, shared design system, crew bundle stays editor-free) is
   still accurate.
5. **Network loss**: publishing is the only network write. If it fails,
   the draft is untouched, the error names the problem, and the sheet is
   marked "not published" until a publish succeeds. Nothing is lost by
   closing the app. **Re-checked, FR-192 (2026-10-20): still accurate** —
   `api.ts`'s `ApiError`/`request()` and `EditorApp.tsx`'s
   `noticeFromError` (status 0 → "No connection. Nothing was lost; try
   again when you are back in signal.") match this description, no drift
   found.

## Calls the editor makes

Table below is from 2026-09-14 and lists only the first few endpoints; the
editor's `api.ts` now exposes ~20 (crew, cast, locations, members, history,
seen reports, actuals, cancel/restore, PDF import, …). Not rewritten row by
row here — out of scope for FR-192 — but flagged so it isn't read as
exhaustive.

| Action | Call |
|---|---|
| verify connection, list productions | `GET /api/v1/productions` (bearer) |
| create production | `POST /api/v1/productions` |
| first publish | `POST /api/v1/productions/{id}/call-sheets` with `initial_revision` |
| later publish | `POST /api/v1/call-sheets/{id}/revisions` |
| share link | `viewer?sheet=<id>&api=<base>` (FR-11 adds QR) |

## Consequences

- Types for create payloads join `src/types.ts`; the API client is a thin
  fetch wrapper with the bearer header.
- An end-to-end Playwright test runs the real backend (uvicorn against the
  test Postgres) and drives the editor: connect, create production, fill a
  day, publish A, change the crew call, publish B, open the viewer link and
  see REV B. CI already has Postgres.
- Drafts are per phone. Two ADs editing the same day is a FR-15 problem.

## Revisit when

FR-12 lands (Connect screen goes away), or FR-15 needs shared drafts, or
the single page grows past what a phone can scroll comfortably (then
sections become steps). **Update, FR-192 (2026-10-20): the first trigger
fired on a wrong prediction.** FR-12 landed 2026-09-14, but Connect did not
go away — it narrowed to the admin gesture and the sign-in-not-configured
fallback (Decision 3 above). The "single page" trigger is also moot: the
editor is no longer a single scrolling page (Decision 4 above), it is
`route.ts`'s hash-routed set of screens, each already scoped to one
concern rather than one long page. FR-15 (shared drafts) has not shipped;
that half of this section still stands.

# ADR-003: The AD editor

Date: 2026-09-14. Status: accepted (founder decisions in session). Serves
FR-10; BRIEF Q1 (who assembles the sheet) and Q7 (smallest thing that
proves the wedge).

## Context

The crew side works: a link opens a call sheet on a phone, offline, with
hot revisions. The AD side is curl. The editor is the first screen an AD
touches, on set, on a phone, often at 05:30 with a weather change.

## Decisions

1. **Scope v1**: production (pick or create), shoot day (date, day X of Y,
   unit), revision fields (crew call, shooting call, sunrise, sunset,
   weather, safety notes), schedule items (scene, INT/EXT, DAY/NIGHT, set,
   pages in eighths) with reorder and delete. No cast calls, no contacts
   (FR-14), no locations.
2. **Draft lives on the phone, the server sees only publishes.** The draft
   is stored in IndexedDB (store `drafts`, keyed by a local id) on every
   change. Publish creates an immutable revision through the existing API:
   the first publish creates the call sheet (revision A), later publishes
   add B, C, ... via `POST /call-sheets/{id}/revisions`. There are no draft
   endpoints; the API stays as it is.
3. **Access until FR-12**: a Connect screen takes the API base and the
   bearer token once and keeps them in `localStorage`. Marked temporary in
   the UI; FR-12 replaces it with Supabase Auth.
4. **Where it lives**: a second Vite entry, `editor.html`, in the same
   project and design system. The crew viewer bundle stays free of editor
   code. No router; the editor is one scrolling page with sections.
5. **Network loss**: publishing is the only network write. If it fails,
   the draft is untouched, the error names the problem, and the sheet is
   marked "not published" until a publish succeeds. Nothing is lost by
   closing the app.

## Calls the editor makes

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
sections become steps).

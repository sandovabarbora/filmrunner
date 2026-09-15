# Status

Updated: 2026-09-15 13:14 (13:00 shift)

## today

- 09:00 · FR-11 · frontend — done: QR code added to the editor's publish flow (PR #45, merged).
- 11:00 · FR-18 · frontend — done (code side): crew photo upload shipped (PR #48, open); gated on INBOX #4 (Supabase Storage bucket + secret) before it works for real.
- 13:00 · FR-19 · tech-lead — done: geocoding, computed sunrise/sunset, a weather suggestion, and a nearest-hospital suggestion for locations, using keyless providers (PR #51, open).
- 15:00 · FR-16 · frontend — ship Web Push notifications on revision publish (VAPID keys as a Fly secret) so crew are told when a call sheet changes.
- 17:00 · FR-7 · security — verify each of the three founding-commit security fixes is actually in place and flip the item's own `state` to `done`.

No open PRs at the start of this shift touched FR-19's own files, so nothing was skipped for depending on one still open. PR #47 (`feat/print-call-sheet`) and PR #48 (`feat/fr-18-crew-photo`) are open from earlier shifts, unrelated to this shift's work. Backlog refill not needed (still 3+ ready+gated:no/partial items: FR-16, FR-7, FR-5).

## pm
- summary: unchanged this shift. FR-3 customer discovery plan delivered (docs/research/discovery-plan.md, PR #11); FR-2 teardown (docs/research/competitive-teardown.md, PR #8) stands. FR-1 (BRIEF.md v0.1) still in-progress, blocked on the founder adding the June 2026 source brief to the repo.
- tests: n/a (research/planning docs, no executable code)
- blockers: `WebFetch`/`WebSearch` remain blocked by this session's egress proxy for most external domains (vendor pages, and now also confirmed for `timeanddate.com` and `api.sunrise-sunset.org` — see engineering below).
- needs_approval: yes — INBOX #1 (recruit and invite five Prague interview candidates; needs the founder's own network and identity, not doable by the routine)

## engineering (tech-lead + frontend)
- summary: FR-19 delivered this shift (PR #51, branch `feat/fr-19-location-services`, open): `docs/adr/ADR-006-location-services.md` picks OpenStreetMap Nominatim (geocoding), an in-process NOAA sunrise-equation formula (no external call), Open-Meteo (weather), and Overpass (nearest hospital) — all free and keyless, so no INBOX item was needed. `Location` gains `geocoded_display_name` (migration `d353e6845c8e`), filled on create/update and re-filled only when the address itself changes. New editor **Locations** tab (name, address, parking notes, nearest hospital) shows "not resolved, check the address" when the geocoder misses instead of silently trusting an unverified address — the dod's own failure case. Each schedule item's Set row gets a location picker (backend already had `location_id`; only the UI was missing). Sunrise/sunset auto-fill on publish from the day's first located scene only when the AD leaves both fields blank — a typed value always wins. Weather and nearest-hospital are "Suggest" buttons next to the existing free-text fields; nothing autofills without an explicit "Use". Every external call (`app/services/geocoding.py`, `weather.py`, `hospitals.py`) has a 5s timeout and returns `None` on any failure rather than raising. `seed_demo.py`'s location now carries hand-set coordinates (documented why: the script must run without guaranteed internet) rather than a live geocode. Carried over: FR-18 (PR #48) and FR-8/FR-11 status unchanged from the 11:00 shift's notes; PR #47 untouched.
- tests: backend — 67/67 pass against a real local Postgres (28 new): `test_astronomy.py` (sunrise-before-sunset year-round, day length longest/shortest at the solstices with DST-correct local time, plus a wide ±20min cross-check against commonly-published Prague solstice times — flagged in the ADR as *not* independently verified against a live source this shift, since `timeanddate.com` and `api.sunrise-sunset.org` are both egress-blocked here); `test_location_services.py` (geocoding/weather/hospital services, every external call mocked: success, no match, timeout, malformed response); `test_locations.py` (router: geocode-on-create, re-geocode-only-when-address-changes, both suggestion endpoints, sunrise/sunset auto-fill and the case where the AD already typed a value). `npm run typecheck` and `npm run build` clean. Verified live against a real build, a real uvicorn+Postgres API, and the real (blocked) network: adding an address genuinely fails to geocode in this sandboxed environment (403 from the egress proxy), and the editor correctly shows the "not resolved" fallback rather than hanging — the failure case exercised for real, not mocked. Committed `frontend/tests/test_locations_e2e.py` (pytest-playwright, for CI where egress is unrestricted); this shift's own `pytest-playwright` browser fixture can't download its pinned Chromium build here (same known gap FR-18 noted), so verification instead used a one-off script against the pre-installed `/opt/pw-browsers/chromium` — all checks passed.
- blockers: none for FR-19 itself. Noted for a future shift: astronomical accuracy is unverified against a live source (egress-blocked); revisit once egress allows fetching a reference.
- needs_approval: no (FR-19 needed no INBOX item — carried over from earlier shifts: INBOX #4 for FR-18's Supabase Storage bucket/secret still needs the founder)

## security (gate)
- summary: no gate run yet; checklist is FR-5 (still ready, not yet picked up). FR-7's three dod bullets are each individually marked done in BACKLOG.md (delivered piecemeal in other PRs), but the item's own `state:` was never flipped from `ready` — planned for the 17:00 shift today.
- tests: n/a
- blockers: none
- needs_approval: no

## marketing
- summary: nothing started; FR-6 still blocked on FR-1 (in-progress) and FR-2 (done).
- tests: n/a
- blockers: FR-1
- needs_approval: no

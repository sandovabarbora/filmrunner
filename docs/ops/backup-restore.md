# Backups and the restore path (FR-53)

What can be lost, where it lives, and how to get it back. Written 2026-09-22; re-check the plan facts when the Supabase plan changes.

## Where the data is

| What | Where | Notes |
|---|---|---|
| Everything the app shows (productions, contacts, crew, cast, locations, days, revisions, personal calls, photos, push subscriptions, read receipts) | **Supabase Postgres**, project `filmrunner` (eu-west-1), one database | The API on Fly holds nothing; it can be redeployed from `main` any time. |
| Sign-in users | Supabase Auth in the same project | Recreated by signing in again; memberships are by e-mail, so a user who re-registers gets their productions back. |
| Secrets | Fly secrets (`fly secrets list -a filmrunner-api`) and the founder's `~/.config/filmrunner/` | Not recoverable from anywhere else — see "Secrets" below. |

## What the platform keeps

- **Supabase Free plan: no automatic backups.** Daily backups (7-day retention) start on the Pro plan; point-in-time recovery is a paid add-on on top of that. Until the project is on Pro, **the only backup is the one we make.**
- Fly keeps nothing of ours (stateless machine).
- GitHub has the code and the migrations; a fresh database can be brought to the current schema with `alembic upgrade head` (the release command does it on every deploy).

## Two backups, two purposes

### 1. Per-production JSON through the API (no database access needed)

`backend/scripts/production_backup.py` exports one production — or all of them — to JSON using the service token, and imports a file into a new (or an existing **empty**) production. It carries what the crew sees: production, contacts, crew, cast, locations with coordinates, members, every day with its current revision (calls, sun, weather, safety, head of day, scenes, cast calls, personal calls) and the day status. It does **not** carry revision history, push subscriptions, read receipts, photos or personal tokens (crew get new links after a restore).

```sh
cd backend
python -m scripts.production_backup export --all --out-dir ~/FilmRunner-backups/$(date +%F)
python -m scripts.production_backup import ~/FilmRunner-backups/2026-09-22/<id>.json            # new production
python -m scripts.production_backup import <file>.json --into <empty production id>             # refused if it has days or crew
```

Use it: before a risky migration, before deleting anything, weekly during a pilot. It works against a healthy API; it is the fastest way to undo "I deleted the wrong production".

### 2. A full `pg_dump` (everything, including history and photos)

Needs the database URL (the one in Fly secrets as `FILMRUNNER_DATABASE_URL`; never paste it into chat or the repo). From the founder's Mac with `pg_dump` 15+ installed (`brew install libpq`):

```sh
# the URL is the Supabase *session pooler* one, sslmode=require
pg_dump "$FILMRUNNER_DATABASE_URL" --no-owner --no-privileges -Fc -f ~/FilmRunner-backups/$(date +%F).dump
```

Restore into a fresh database (a new Supabase project, or the same one after `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`):

```sh
pg_restore --no-owner --no-privileges -d "$NEW_DATABASE_URL" ~/FilmRunner-backups/2026-09-22.dump
alembic -x url="$NEW_DATABASE_URL" current   # must show the head revision; if not: alembic upgrade head
fly secrets set -a filmrunner-api FILMRUNNER_DATABASE_URL="$NEW_DATABASE_URL"   # Fly restarts the API
```

Personal tokens, push subscriptions and photos survive this path; crew links keep working.

Keep the dumps outside the repo (they contain phone numbers) — an encrypted folder in iCloud/Drive is fine. A weekly reminder is enough for a pilot; move to the Pro plan before a paying production.

## Rotating the database password (still to do — it passed through chat once)

1. Supabase dashboard → Project Settings → Database → **Reset database password** → copy the new one.
2. Build the new URL (same host/port/user, new password, `?sslmode=require`).
3. `fly secrets set -a filmrunner-api FILMRUNNER_DATABASE_URL="postgresql+psycopg://…"` — Fly redeploys; check `curl https://filmrunner-api.fly.dev/healthz` and one sheet.
4. Update the local `backend/.env` if it points at the hosted database (it should not: local dev uses Docker).

## Secrets: what is recoverable and how

| Secret | Lost → | Recreate |
|---|---|---|
| `FILMRUNNER_DATABASE_URL` | API down | Reset the DB password (above), set again. |
| `FILMRUNNER_API_BEARER_TOKEN` | scripts and the admin path stop | Generate a new random string, `fly secrets set`, update `~/.config/filmrunner/api_token`. |
| `FILMRUNNER_VAPID_PUBLIC_KEY` / `_PRIVATE_KEY` | push stops | `python -m scripts.generate_vapid_keys`, set both; every phone must re-enable notifications. |
| `FILMRUNNER_ANTHROPIC_API_KEY` | PDF import falls back to heuristics (still works) | New key in the Anthropic console, set. |
| Supabase anon key / URL (GitHub Actions variables) | sign-in stops on Pages | Project Settings → API → copy; update the repository variables. |

## Drills

- 2026-09-22: JSON round trip verified in the test suite (`backend/tests/test_production_backup.py`): export → import → the crew's sheets are identical field for field; import into a non-empty production is refused.
- 2026-10-15 (FR-177): the `pg_dump`/`pg_restore`/`alembic current` commands above were drilled verbatim against a disposable **local** Postgres 16 (`postgresql-16` installed directly in the routine's sandbox, not Docker — Docker's daemon isn't available there; `docker-compose.yml`'s own `postgres:16` image is the equivalent for a real dev machine). Ran `alembic upgrade head`, then seeded real rows in all 16 application tables by running the API locally against it and exercising it end to end (`app/seed_demo.py` for the base production/crew/location/call sheet, plus direct API calls for a cast member, a second and third revision with crew-call and cast-call entries, a production member, a contact photo, a Web Push subscription, a revision view, and — after generating a throwaway local VAPID keypair — one real `distribution_log` delivery-failure row from the push attempt against a fake endpoint). Dumped with the exact `pg_dump ... --no-owner --no-privileges -Fc` command above, then `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, then the exact `pg_restore --no-owner --no-privileges -d ...` command: **zero errors or warnings**, nothing adjusted. `alembic -x url=... current` reported the head revision (`7feea1cfc0e6`) immediately after restore, no manual fix-up needed — the `-x url=` flag the doc documents works as written. Diffed an MD5 checksum of every row's key fields (id + distinguishing columns, built with `string_agg`) across all 15 non-`alembic_version` tables, before dump and after restore: **identical in every table**, confirming the data came back byte-for-byte, not just that the commands exited 0. No flag was wrong or outdated for this Postgres version (client and server both 16.15/16). The one thing this drill could not cover: the hosted Supabase project itself (needs the founder's own database URL, per `TEAM.md` — the routine cannot hold it) — that half stays open, scratch-Supabase-project drill still to do before the first paying production.

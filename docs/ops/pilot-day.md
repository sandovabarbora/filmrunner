# Pilot day runbook

For whoever keeps a shoot day running, written for a first-time reader. The call is at 05:00 Prague. Crew phones read the sheet from the API (Fly, app `filmrunner-api`) and the app from GitHub Pages; the data is in Supabase Postgres.

## T-24h (founder)

1. **Deploy, if at all, now.** Run `scripts/deploy_api.sh --dry-run`, then `scripts/deploy_api.sh` on a clean `main`. It refuses 22:00-07:00 Prague unless given `--force-window`. Nothing is deployed after this until the shoot is over.
2. **Freeze the app:** `gh variable set PILOT_FREEZE --body true`. Pages then skips its deploy.
3. **Pause the routines** at https://claude.ai/code/routines: switch off the shifts and the morning brief (ids in `docs/company/TEAM.md`), so no agent works on the day.
4. **Supabase dashboard** (project `filmrunner`):
   - The project is active, not paused. Free projects pause after a week of inactivity.
   - Take a backup: the Free plan has none. Follow "A full `pg_dump`" in `docs/ops/backup-restore.md`.
   - Database, Reports: connections are well below the pooler's limit of 15 (the API uses at most 10).
5. **Monitors** are on, each alerting to a phone app push, not email, which nobody reads at 04:30. Free options: [UptimeRobot](https://uptimerobot.com/pricing/) Free (50 monitors, 5-minute checks, keyword monitors, allowed for commercial use; push through its app, or Pushover or Pushbullet) or [Better Stack](https://betterstack.com/pricing) Free Tier (10 monitors; "personal projects"). Neither page confirms push on the free plan, so **prove it**: add a monitor on a URL that returns 404 and see the phone buzz, then delete it.

   | Check | Monitor type, URL | Passes when | Interval, timeout | Red means |
   |---|---|---|---|---|
   | `healthz` | Keyword, `https://filmrunner-api.fly.dev/healthz` | 200 containing `"status":"ok"` | shortest free (5 min), 30 s | The API process is down |
   | `readyz` | HTTP, `https://filmrunner-api.fly.dev/readyz` | 200 | shortest free (5 min), 30 s | The API cannot reach the database |
   | `pages` | Keyword, `https://sandovabarbora.github.io/filmrunner/` | 200 containing `FilmRunner` | shortest free (5 min), 30 s | The app does not load without a cached copy |

6. `fly status -a filmrunner-api` shows exactly one machine in total, started or stopped. A stopped second one would start under load, and the rate limiter and connection pool assume one.

## T-1h (04:00)

1. The nightly check finished before now, and is green: `gh run list --workflow pilot-readiness.yml --limit 1`. Its Deploy line may be green with main ahead, which is fine as long as no `backend/` commit is waiting.
2. `curl -s https://filmrunner-api.fly.dev/readyz` answers `"status":"ok"`.
3. Open your own crew link on a phone: today's sheet, right revision.
4. The AD has the **fallback on the phone already**: the day's **PDF** saved to the phone and **Send day as text** ready. Both come from the API, so they cannot be fetched during an outage.

## On set

- Watch **REV A opened by N of M** on the day screen; **nudge** whoever has not opened it.
- Keep the phone with the monitor app on loud. Do not deploy, merge or run migrations. Do not paste crew links into any chat: each one is a credential.

## Incident

1. **Tell the AD within 2 minutes**: "FilmRunner is having a problem. Sheets already opened still work. Stand by." A phone that opened its sheet keeps it offline.
2. **Look:**
   ```sh
   curl -s -m 10 -w ' %{http_code}\n' https://filmrunner-api.fly.dev/healthz
   curl -s -m 10 -w ' %{http_code}\n' https://filmrunner-api.fly.dev/readyz
   fly logs -a filmrunner-api --no-tail
   ```
   Log lines read `GET /public/crew/{token}/next 200 42ms request_id=...`. Paths and tokens are deliberately absent.
3. **Act on what you see:**

   | healthz | readyz | Means | Do |
   |---|---|---|---|
   | fails | fails | API down | `fly status -a filmrunner-api`, then `fly machine restart <id> -a filmrunner-api`. Started just after a deploy: roll back. |
   | 200 | 503 | Database unreachable, or a wedged connection pool | Look at the Supabase dashboard: paused means Restore; down means its status page. If Supabase is healthy, restart the machine: `fly machine restart <id> -a filmrunner-api`. |
   | 200 | 200 | API fine | Check Pages. Many 500s since a deploy: roll back. Many 429s: see below. |

   **429s on one Wi-Fi:** the whole crew shares one address and hit the rate limit. The limiter lives in memory, so `fly machine restart <id> -a filmrunner-api` clears it at once, at the cost of a brief outage. Ask people to stop reloading, or to use mobile data, which has another address.

   **One person's trouble:** tokens are absent from the logs by design, so the logs cannot show one person's requests. Check in the app: Crew has their number and link, and the day screen shows whether they opened the sheet. Have them open a fresh copy of their link.

   **A fix has to ship:** the freeze stops it. For the API, `scripts/deploy_api.sh --force-window` overrides the freeze and the hour. For the app, `gh variable delete PILOT_FREEZE`, then `gh workflow run pages.yml`, then set the freeze again as in T-24h.

4. **Not fixed 15 minutes after the report, or 30 minutes before the call, whichever comes first: go to the fallback.** Do not wait longer for a fix.

## Fallback

The AD sends the saved PDF and the day's text to the crew's WhatsApp group: "FilmRunner is down, this is the current call sheet: REV x." From that moment the group message is the truth, until the AD says otherwise. Later changes go to the group by hand. Afterwards, publish them in FilmRunner so it matches, and write down what happened.

## Rollback

```sh
fly releases --image -a filmrunner-api    # find the last good image; deploy_api.sh also printed it
cd backend && fly deploy --image <image> --skip-release-command
curl -s https://filmrunner-api.fly.dev/healthz    # git_sha is the older commit
```

`--skip-release-command` matters: the older image does not know newer migrations, so `alembic upgrade head` would fail and stop the rollback. The older code then runs on the newer schema, which is safe only for additive migrations (our rule; check `backend/alembic/versions` if the release had one). A release older than FR-223 has no `/readyz`, so it answers 404.

## After the shoot

1. `gh variable delete PILOT_FREEZE`, then `gh workflow run pages.yml`: merges during the freeze are not live until then.
2. Switch the routines back on.
3. Write up the day log (`docs/pilot/pilot-plan.md`, "What we measure") and every workaround anyone used.

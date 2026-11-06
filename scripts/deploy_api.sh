#!/usr/bin/env bash
# Deploy the API from a clean, green main, outside the hours a crew depends on it, and prove the new commit is serving.
# Usage: scripts/deploy_api.sh [--dry-run] [--force-window]
#   --dry-run       run every gate and read the current image, change nothing
#   --force-window  allow 22:00-07:00 Prague, for an incident fix
set -euo pipefail

APP="filmrunner-api"
API="${API:-https://filmrunner-api.fly.dev}"
REPO="sandovabarbora/filmrunner"
POLL_ATTEMPTS=60
POLL_SECONDS=5

dry_run=false
force_window=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    --force-window) force_window=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

refuse() {
  echo "REFUSED: $*" >&2
  exit 1
}

cd "$(dirname "$0")/.."

branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || refuse "on '$branch', not main"
[ -z "$(git status --porcelain)" ] || refuse "the working tree is not clean"
git fetch --quiet origin main
sha="$(git rev-parse HEAD)"
[ "$sha" = "$(git rev-parse origin/main)" ] || refuse "HEAD ${sha:0:7} is not origin/main"

conclusions="$(gh api "repos/$REPO/commits/$sha/check-runs?check_name=ci" --jq '.check_runs[] | (.conclusion // "unfinished")')" \
  || refuse "could not read the CI result for ${sha:0:7}"
[ -n "$conclusions" ] || refuse "CI has no result for ${sha:0:7}"
if grep -qvx success <<<"$conclusions"; then
  refuse "CI is not green for ${sha:0:7}"
fi

hour="$(TZ=Europe/Prague date +%H)"
if [ "$((10#$hour))" -ge 22 ] || [ "$((10#$hour))" -lt 7 ]; then
  [ "$force_window" = true ] || refuse "it is ${hour}:xx in Prague, inside 22:00-07:00; a crew may be opening the sheet. Use --force-window for an incident fix"
fi

previous_image="$(fly releases --image --json -a "$APP" | python3 -c '
import json, sys
releases = json.load(sys.stdin)
print(next((r.get("ImageRef") or r.get("imageRef") for r in releases if (r.get("ImageRef") or r.get("imageRef")) and r.get("Status", "complete") == "complete"), ""))
' || true)"

print_rollback() {
  if [ -n "$previous_image" ]; then
    echo "Rollback (skips the release command: an older image cannot run 'alembic upgrade head' past its own migrations):"
    echo "  cd backend && fly deploy --image $previous_image --skip-release-command"
  else
    echo "Could not read the previous image. Find it with: fly releases --image -a $APP"
    echo "Then: cd backend && fly deploy --image <that image> --skip-release-command"
  fi
}

print_rollback

if [ "$dry_run" = true ]; then
  echo "Dry run: all gates passed for ${sha:0:7}. Would run: (cd backend && fly deploy --build-arg FILMRUNNER_GIT_SHA=$sha)"
  exit 0
fi

if ! (cd backend && fly deploy --build-arg "FILMRUNNER_GIT_SHA=$sha"); then
  echo "fly deploy failed." >&2
  print_rollback >&2
  exit 1
fi

reported_sha() {
  curl -fsS -m 10 "$API/$1" 2>/dev/null \
    | python3 -c 'import json, sys; print(json.load(sys.stdin).get("git_sha", ""))' 2>/dev/null \
    || true
}

for endpoint in healthz readyz; do
  attempt=0
  until [ "$(reported_sha "$endpoint")" = "$sha" ]; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$POLL_ATTEMPTS" ]; then
      echo "/$endpoint did not report ${sha:0:7} within $((POLL_ATTEMPTS * POLL_SECONDS)) s." >&2
      print_rollback >&2
      exit 1
    fi
    sleep "$POLL_SECONDS"
  done
  echo "/$endpoint serves ${sha:0:7}"
done

echo "Deployed ${sha:0:7}."
print_rollback

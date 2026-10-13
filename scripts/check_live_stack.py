"""FR-66: is the deployed stack actually up and serving what the crew needs?

Public, unauthenticated endpoints only — no token is needed and none belongs here. Run by
`.github/workflows/pilot-readiness.yml` (daily and on demand) from a runner with open egress,
because the routine's own sandbox cannot reach `filmrunner-api.fly.dev` at all.

Locally: `API=https://filmrunner-api.fly.dev python3 scripts/check_live_stack.py`
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Callable, Literal

API = os.environ.get("API", "https://filmrunner-api.fly.dev").rstrip("/")
PAGES = os.environ.get("PAGES", "https://sandovabarbora.github.io/filmrunner").rstrip("/")
GITHUB_API = os.environ.get("GITHUB_API", "https://api.github.com/repos/sandovabarbora/filmrunner")
# The browser sends the origin (scheme + host), not the project path GitHub Pages serves us under.
PAGES_ORIGIN = "://".join(PAGES.split("://")[:1] + [PAGES.split("://", 1)[1].split("/", 1)[0]])
TIMEOUT = 20

# "warn" is FR-164: a check that was never able to verify anything (e.g. no SHA reported
# yet) must not render the same as "ok" — only "ok" means something was actually checked
# and passed. Only "fail" counts toward the job's exit code; "warn" does not.
Status = Literal["ok", "warn", "fail"]
MARKS: dict[Status, str] = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
Result = tuple[str, Status, str]


def _status(result: bool | Status) -> Status:
    if isinstance(result, bool):
        return "ok" if result else "fail"
    if result not in ("ok", "warn", "fail"):
        raise ValueError(f"unknown check status {result!r}")
    return result


def fetch(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "filmrunner-live-check", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}


def deploy_staleness_message(deployed_sha: str | None, main_sha: str, compare: dict) -> tuple[Status, str]:
    """Pure formatting/decision logic, unit-tested without a network call.

    `compare` is a GitHub "compare two commits" API response
    (https://docs.github.com/en/rest/commits/commits#compare-two-commits) for
    `deployed_sha...main_sha`: `ahead_by` counts commits on `main_sha` not yet
    reachable from `deployed_sha`, and `commits[0]` is the oldest of those.

    Three distinct outcomes, not two (FR-164): "cannot verify" (no SHA reported yet) is
    neither a verified pass nor a verified failure, and must not collapse into either.
    """
    if deployed_sha is None:
        return "warn", "cannot verify — deployed build predates commit reporting (FR-109)"
    if deployed_sha == main_sha:
        return "ok", f"up to date ({deployed_sha[:7]})"
    ahead_by = compare.get("ahead_by", 0)
    commits = compare.get("commits") or []
    since = commits[0]["commit"]["committer"]["date"] if commits else "unknown"
    return "fail", f"{ahead_by} commits behind main, since {since} (deployed {deployed_sha[:7]}, main {main_sha[:7]})"


def deploy_matches_main() -> tuple[Status, str]:
    status, body, _ = fetch(f"{API}/healthz")
    deployed_sha = json.loads(body or b"{}").get("git_sha")
    if status != 200:
        return "fail", f"healthz returned {status}"
    if deployed_sha is None:
        return deploy_staleness_message(None, "", {})
    gh_headers = {"Accept": "application/vnd.github+json"}
    _, main_body, _ = fetch(f"{GITHUB_API}/commits/main", headers=gh_headers)
    main_sha = json.loads(main_body or b"{}").get("sha", "")
    if not main_sha:
        return "fail", f"could not read main's HEAD sha from {GITHUB_API}/commits/main"
    if deployed_sha == main_sha:
        return deploy_staleness_message(deployed_sha, main_sha, {})
    _, compare_body, _ = fetch(f"{GITHUB_API}/compare/{deployed_sha}...{main_sha}", headers=gh_headers)
    compare = json.loads(compare_body or b"{}")
    return deploy_staleness_message(deployed_sha, main_sha, compare)


def check(name: str, fn: Callable[[], tuple[bool | Status, str]]) -> Result:
    """Any exception is a failure with its text — never a silent 'not verified'."""
    try:
        result, detail = fn()
    except Exception as exc:  # noqa: BLE001
        return name, "fail", f"{exc.__class__.__name__}: {exc}"
    return name, _status(result), detail


def api_health() -> tuple[bool, str]:
    status, body, _ = fetch(f"{API}/healthz")
    data = json.loads(body or b"{}")
    return status == 200 and data.get("status") == "ok", f"{status} {data}"


def api_openapi_has_the_current_surface() -> tuple[bool, str]:
    """The deployed build is the one we think it is: routes added this week must be there."""
    status, body, _ = fetch(f"{API}/openapi.json")
    paths = set(json.loads(body or b"{}").get("paths", {}))
    wanted = {
        "/api/v1/public/crew/{token}/next",                       # FR-32 stable link
        "/api/v1/public/call-sheets/{call_sheet_id}/seen/{token}",  # FR-36 read receipts
        "/api/v1/call-sheets/{call_sheet_id}/actuals",             # FR-65 actual times
        "/api/v1/productions/{production_id}/import/call-sheet-pdf",  # FR-57 PDF import
    }
    missing = sorted(wanted - paths)
    return status == 200 and not missing, f"{status}, {len(paths)} paths" + (f", missing: {missing}" if missing else "")


def unknown_token_is_refused() -> tuple[bool, str]:
    """A guessed personal token must 404, not leak a sheet (FR-13/FR-32)."""
    status, _, _ = fetch(f"{API}/api/v1/public/crew/definitely-not-a-token/next")
    return status == 404, str(status)


def unknown_sheet_is_refused() -> tuple[bool, str]:
    status, _, _ = fetch(f"{API}/api/v1/public/call-sheets/00000000-0000-0000-0000-000000000000")
    return status == 404, str(status)


def push_key_is_configured() -> tuple[bool, str]:
    """Web Push is inert without the VAPID key; the crew would never get a revision alert (FR-16)."""
    status, body, _ = fetch(f"{API}/api/v1/public/push/vapid-key")
    key = json.loads(body or b"{}").get("public_key")
    return status == 200 and bool(key), f"{status}, key {'set' if key else 'MISSING'}"


def cors_allows_the_pages_origin() -> tuple[bool, str]:
    """Without this the crew's sheet cannot load anything from the API."""
    req = urllib.request.Request(
        f"{API}/api/v1/public/push/vapid-key", method="OPTIONS",
        headers={"Origin": PAGES_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            allow = r.headers.get("access-control-allow-origin", "")
            return allow in (PAGES_ORIGIN, "*"), f"{r.status}, allow-origin {allow!r}"
    except urllib.error.HTTPError as exc:
        return False, f"{exc.code}"


def page_serves(path: str, must_contain: str) -> Callable[[], tuple[bool, str]]:
    def run() -> tuple[bool, str]:
        status, body, _ = fetch(f"{PAGES}/{path}" if path else PAGES)
        text = body.decode("utf-8", "replace")
        return status == 200 and must_contain in text, f"{status}, {len(body)} B" + ("" if must_contain in text else f", missing {must_contain!r}")
    return run


def rate_limit_headers_on_refusal() -> tuple[bool, str]:
    """FR-51's guard answers 429 with Retry-After; below the limit it must not fire at all."""
    statuses = [fetch(f"{API}/api/v1/public/push/vapid-key")[0] for _ in range(5)]
    return all(s == 200 for s in statuses), f"5 requests → {statuses}"


CHECKS: list[tuple[str, Callable[[], tuple[bool | Status, str]]]] = [
    ("API health", api_health),
    ("API serves this week's routes", api_openapi_has_the_current_surface),
    ("Unknown personal token → 404", unknown_token_is_refused),
    ("Unknown call sheet → 404", unknown_sheet_is_refused),
    ("Web Push key configured", push_key_is_configured),
    ("CORS allows the Pages origin", cors_allows_the_pages_origin),
    ("Pages: crew app", page_serves("", "FilmRunner")),
    ("Pages: editor", page_serves("editor.html", "FilmRunner")),
    ("Pages: landing", page_serves("landing.html", "FilmRunner")),
    ("Pages: privacy note", page_serves("privacy.html", "Supabase")),
    ("A handful of requests is not rate limited", rate_limit_headers_on_refusal),
    ("Deploy matches main (FR-109)", deploy_matches_main),
]


def main() -> int:
    results = [check(name, fn) for name, fn in CHECKS]
    failed = [r for r in results if r[1] == "fail"]
    lines = [f"## Live stack — {'all good' if not failed else f'{len(failed)} failing'}", "",
             f"API `{API}` · Pages `{PAGES}`", "", "| Check | Result | Detail |", "|---|---|---|"]
    for name, status, detail in results:
        lines.append(f"| {name} | {MARKS[status]} | `{detail}` |")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

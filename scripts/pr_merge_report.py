"""FR-114: merge-readiness report for the growing open-PR queue.

Every shift's own STATUS.md note already says, by hand, whether a PR's `ci` is green and
which TEAM.md merge-rule bucket it falls under (the auto-merge reversible-document path vs.
the founder-must-merge path for backend/frontend/scripts/workflows/decision docs) -- copied
fresh into STATUS.md every run. This script answers the same question from the PR's own
changed files, not a shift's memory or a PR's title, so the founder (or a shift) can see it
at a glance:

    GH_TOKEN=<token> python3 scripts/pr_merge_report.py

Requires the `gh` CLI, authenticated (GitHub Actions runners ship it with `GH_TOKEN` already
set from `github.token`; this sandbox does not have `gh` installed, so `main()`/`fetch_open_prs()`
are verified via a workflow_dispatch run rather than locally -- see
`.github/workflows/pr-merge-report.yml`). The classification logic itself
(`classify_bucket`, `flag_for_attention`, `ci_conclusion`, `format_table`) takes no live
`gh` output as a hard dependency and is unit-tested against fixed fixtures in
`scripts/tests/test_pr_merge_report.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field

# TEAM.md, "auto-merge (reversible...)" bucket (2026-09-17 decision): a PR touching only
# these paths auto-merges. Everything else -- backend/, frontend/, scripts/,
# .github/workflows/, and the decision documents (docs/adr/**, BRIEF.md, TEAM.md,
# DECISIONS.md) -- waits for the founder. A path this list doesn't name is never guessed
# as safe: it falls through to "founder-merge" by default (see classify_bucket).
REVERSIBLE_EXACT = {
    "docs/company/STATUS.md",
    "docs/company/INBOX.md",
    "docs/company/LOG.md",
    "docs/company/BACKLOG.md",
    ".github/pull_request_template.md",
}
REVERSIBLE_DIRS = (
    "docs/research/",
    "docs/marketing/",
    "docs/gates/",
)


@dataclass
class PullRequest:
    number: int
    title: str
    created_at: str
    mergeable_state: str  # gh's mergeStateStatus, lowercased: clean/dirty/behind/blocked/unknown/...
    ci: str  # success/failure/pending/unknown
    files: list[str] = field(default_factory=list)


def _is_reversible_path(path: str) -> bool:
    return path in REVERSIBLE_EXACT or any(path.startswith(d) for d in REVERSIBLE_DIRS)


def classify_bucket(files: list[str]) -> str:
    """'auto-merge' only when every changed file is on the reversible allowlist; otherwise
    'founder-merge' (the safe default -- an unrecognised path is never treated as reversible).
    'unknown' only when the PR's file list itself couldn't be read."""
    if not files:
        return "unknown"
    return "auto-merge" if all(_is_reversible_path(f) for f in files) else "founder-merge"


def ci_conclusion(status_check_rollup: list[dict]) -> str:
    """Collapse `gh`'s statusCheckRollup into the `ci` check's own conclusion. TEAM.md's
    merge ruleset gates on `ci` alone, so other checks (e.g. Claude Approvals) are not
    consulted here."""
    for check in status_check_rollup:
        name = check.get("name") or check.get("context")
        if name == "ci":
            value = (check.get("conclusion") or check.get("state") or "").lower()
            return value or "pending"
    return "unknown"


def flag_for_attention(pr: PullRequest) -> str | None:
    """A distinct flag for a PR that is not simply "waiting on a merge click" -- so the
    founder never discovers a conflict only after already clicking merge."""
    if pr.mergeable_state in ("dirty", "conflicting"):
        return "CONFLICT"
    if pr.ci == "failure":
        return "CI RED"
    if pr.ci in ("pending", "in_progress", "queued"):
        return "CI RUNNING"
    return None


def format_table(prs: list[PullRequest]) -> str:
    """One glance-able table, oldest PR first (matches STATUS.md's own "waiting on you" order)."""
    if not prs:
        return "No open PRs."
    header = f"{'#':>5}  {'opened':<20}  {'ci':<9}  {'merge':<11}  {'bucket':<14}  {'flag':<10}  title"
    lines = [header, "-" * len(header)]
    for pr in sorted(prs, key=lambda p: p.created_at):
        bucket = classify_bucket(pr.files)
        flag_str = flag_for_attention(pr) or ""
        title = pr.title if len(pr.title) <= 60 else pr.title[:57] + "..."
        lines.append(
            f"#{pr.number:<4} {pr.created_at:<20}  {pr.ci:<9}  {pr.mergeable_state:<11}  "
            f"{bucket:<14}  {flag_str:<10}  {title}"
        )
    return "\n".join(lines)


def fetch_open_prs() -> list[PullRequest]:
    """Shell out to `gh pr list --json ...` for every open PR's number, title, age, merge
    state, CI rollup, and changed files."""
    raw = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,createdAt,mergeStateStatus,statusCheckRollup,files",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    prs = []
    for item in json.loads(raw):
        prs.append(
            PullRequest(
                number=item["number"],
                title=item["title"],
                created_at=item["createdAt"],
                mergeable_state=str(item.get("mergeStateStatus", "unknown")).lower(),
                ci=ci_conclusion(item.get("statusCheckRollup") or []),
                files=[f["path"] for f in item.get("files") or []],
            )
        )
    return prs


def main() -> int:
    print(format_table(fetch_open_prs()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

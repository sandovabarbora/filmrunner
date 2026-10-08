"""FR-152: a scheduled dependency vulnerability scan, so a stale advisory
database stops needing a fresh one-off backlog item every few days.

FR-91/100/110/117/124 each re-ran `pip-audit`/`npm audit` by hand purely
because the advisory database moved, independent of any code change here
(FR-110 found 10 new `pyjwt` CVEs a day after FR-91's own baseline; FR-117
found 13, not 10, the day after that). `.github/workflows/dependency-audit.yml`
runs this script weekly and on demand, the same `schedule: cron` +
`workflow_dispatch` pattern `pilot-readiness.yml` already uses.

Any finding beyond the already-documented, accepted risk below (currently:
`xlsx`'s two advisories, which have no fix on the npm registry — see
`docs/research/dependency-audit-2026-09.md`) fails the run (non-zero exit,
flagged in `$GITHUB_STEP_SUMMARY`) rather than passing silently, per this
item's own failure case. A scanner that cannot reach its advisory database
also fails the run rather than being misread as "clean" (FR-91's own
failure case, carried over here).

This script does not write to `docs/research/dependency-audit-2026-09.md`
itself: every workflow in this repo is `permissions: contents: read` and
none commits back to the tree today (checked directly — `pr-merge-report.yml`,
`check-backlog-duplicates.yml`, `desk-research-reverify.yml`, `pilot-readiness.yml`
all only print to the run summary or upload an artifact). Giving a scheduled,
unattended job write access to the repo would be a new capability, not a
narrow extension of this item's own scope — a failing/flagged run is the
signal, same as `pilot-readiness.yml`'s failing checks already are, and a
shift or the founder does the actual write, same as every prior pass.

Locally: `python3 scripts/check_dependency_audit.py` (needs `pip-audit` on
`PATH` and `npm` with `frontend/node_modules` installed).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

BACKEND_REQUIREMENTS = "backend/requirements.txt"
FRONTEND_DIR = "frontend"

# Findings accepted as an open, documented risk — anything else is "new"
# and must fail the run. Keep this in sync with
# docs/research/dependency-audit-2026-09.md's own accepted-risk notes.
ACCEPTED_BACKEND_IDS: frozenset[str] = frozenset()
ACCEPTED_FRONTEND_IDS: frozenset[str] = frozenset(
    {
        "GHSA-4r6h-8v6p-xvw6",  # xlsx prototype pollution, no fix on the npm registry (FR-91/111/124)
        "GHSA-5pgg-2g8v-p4x9",  # xlsx ReDoS, no fix on the npm registry (FR-91/111/124)
    }
)


def extract_pip_finding_ids(data: dict) -> list[str]:
    """`pip-audit -f json`'s shape: {"dependencies": [{"vulns": [{"id": ...}]}]}."""
    return sorted({v["id"] for dep in data.get("dependencies", []) for v in dep.get("vulns", [])})


def extract_npm_finding_ids(data: dict) -> list[str]:
    """`npm audit --json`'s shape nests advisory URLs in each finding's `via` list.

    `via` entries that are plain strings (not dicts) name another package in the
    chain, not an advisory of their own, and carry no id to extract.
    """
    ids: set[str] = set()
    for info in data.get("vulnerabilities", {}).values():
        for via in info.get("via", []):
            if isinstance(via, dict) and via.get("url"):
                ids.add(via["url"].rsplit("/", 1)[-1])
    return sorted(ids)


def classify(found_ids: list[str], accepted_ids: frozenset[str]) -> tuple[bool, list[str]]:
    """Pure decision logic: is every finding already a documented, accepted risk?"""
    new = sorted(set(found_ids) - accepted_ids)
    return not new, new


def run_pip_audit() -> tuple[bool, list[str], str]:
    """Returns (ran_ok, finding_ids, human-readable detail)."""
    try:
        proc = subprocess.run(
            ["pip-audit", "-r", BACKEND_REQUIREMENTS, "-f", "json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return False, [], "pip-audit is not installed"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout or "no output").strip()[:500]
        return False, [], f"could not parse pip-audit output (exit {proc.returncode}): {detail}"
    ids = extract_pip_finding_ids(data)
    return True, ids, f"{len(data.get('dependencies', []))} packages checked, {len(ids)} finding id(s)"


def run_npm_audit() -> tuple[bool, list[str], str]:
    try:
        proc = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=FRONTEND_DIR,
        )
    except FileNotFoundError:
        return False, [], "npm is not installed"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout or "no output").strip()[:500]
        return False, [], f"could not parse npm audit output (exit {proc.returncode}): {detail}"
    if data.get("error"):
        return False, [], f"npm audit reported an error rather than a report: {data['error']}"
    ids = extract_npm_finding_ids(data)
    total = data.get("metadata", {}).get("vulnerabilities", {}).get("total", len(ids))
    return True, ids, f"{total} finding(s) reported"


def report_section(label: str, ran_ok: bool, ids: list[str], detail: str, accepted: frozenset[str]) -> tuple[bool, str]:
    if not ran_ok:
        return False, f"- ❌ {label}: scanner did not run — {detail} (never read as a clean scan)"
    clean, new = classify(ids, accepted)
    if clean:
        shown = ", ".join(sorted(accepted)) or "none"
        return True, f"- ✅ {label}: {detail}, no finding beyond the documented accepted risk ({shown})"
    return (
        False,
        f"- ❌ {label}: {detail}, **new/unaccepted finding(s)**: {', '.join(new)} — "
        "add a dated section to docs/research/dependency-audit-2026-09.md and open a PR, "
        "same as FR-91/100/110/117/124",
    )


def main() -> int:
    backend_ok, backend_ids, backend_detail = run_pip_audit()
    frontend_ok, frontend_ids, frontend_detail = run_npm_audit()

    backend_clean, backend_line = report_section(
        "Backend (`pip-audit`)", backend_ok, backend_ids, backend_detail, ACCEPTED_BACKEND_IDS
    )
    frontend_clean, frontend_line = report_section(
        "Frontend (`npm audit`)", frontend_ok, frontend_ids, frontend_detail, ACCEPTED_FRONTEND_IDS
    )

    report = "\n".join(["## Dependency audit (FR-152)", "", backend_line, frontend_line])
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 0 if (backend_clean and frontend_clean) else 1


if __name__ == "__main__":
    sys.exit(main())

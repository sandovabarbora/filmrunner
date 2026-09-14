"""Check a branch name and a PR title against the team conventions.

Usage:
    python scripts/check_conventions.py <branch> <pr-title>

Exit code 0 when both comply, 1 otherwise. Conventions live in
docs/company/TEAM.md; this script is what CI actually enforces.
"""

from __future__ import annotations

import re
import sys

TYPES = ("feat", "fix", "docs", "chore", "refactor", "test", "ci")
_BRANCH = re.compile(rf"^({'|'.join(TYPES)})/[a-z0-9][a-z0-9._-]*$")
_TITLE = re.compile(rf"^({'|'.join(TYPES)})(\([a-z0-9-]+\))?: \S(?:.*[^.])?$")


def check_branch(name: str) -> str | None:
    """Return a problem description for a branch name, or None when it complies."""
    if _BRANCH.match(name):
        return None
    return f"branch '{name}' must look like <type>/<what-it-does>, type in {TYPES}, lowercase"


def check_title(title: str) -> str | None:
    """Return a problem description for a PR title, or None when it complies."""
    if _TITLE.match(title):
        return None
    return f"title '{title}' must look like 'type(scope): subject' with type in {TYPES}, no trailing period"


def main(branch: str, title: str) -> int:
    """Print every problem found; return 1 if any, else 0."""
    problems = [p for p in (check_branch(branch), check_title(title)) if p]
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))

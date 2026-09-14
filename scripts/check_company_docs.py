"""Validate the machine-readable parts of docs/company.

BACKLOG.md and INBOX.md are read by the daily routine to decide what to
work on and what is approved. This checker keeps their grammar strict so
a typo in a state never silently hides or unlocks work.

Usage:
    python scripts/check_company_docs.py [path/to/docs/company]

Exit code 0 when clean, 1 when any problem is printed.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROLES = {"pm", "tech-lead", "frontend", "marketing", "security", "qa"}
BACKLOG_STATES = {"ready", "in-progress", "blocked", "done"}
GATED_VALUES = {"yes", "no", "partial"}
INBOX_STATES = {"pending", "approved", "rejected", "done"}
INBOX_FIELDS = ("state", "what", "why", "risk", "proposal")

_HEADING = re.compile(r"^## (?P<id>FR-\d+|#\d+) · (?P<role>[a-z-]+) · (?P<title>.+)$")
_FIELD = re.compile(r"^- (?P<key>[a-z]+):\s*(?P<value>.*)$")
_DOD_LINE = re.compile(r"^  - (?P<text>.+)$")


@dataclass
class Item:
    """One `## id · role · title` block and its bullet fields."""

    item_id: str
    role: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)
    dod: list[str] = field(default_factory=list)


def parse_items(text: str) -> list[Item]:
    """Split a company doc into items.

    Args:
        text: Full markdown content of BACKLOG.md or INBOX.md.

    Returns:
        Items in document order; lines before the first heading are ignored.
    """
    items: list[Item] = []
    current: Item | None = None
    in_dod = False
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = Item(heading["id"], heading["role"], heading["title"].strip())
            items.append(current)
            in_dod = False
            continue
        if current is None:
            continue
        if in_dod and (dod_line := _DOD_LINE.match(line)):
            current.dod.append(dod_line["text"].strip())
            continue
        in_dod = False
        if bullet := _FIELD.match(line):
            current.fields[bullet["key"]] = bullet["value"].strip()
            in_dod = bullet["key"] == "dod"
    return items


def _common_problems(items: list[Item]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item.item_id in seen:
            problems.append(f"duplicate id {item.item_id}")
        seen.add(item.item_id)
        if item.role not in ROLES:
            problems.append(f"{item.item_id}: unknown role '{item.role}' (allowed: {sorted(ROLES)})")
    return problems


def check_backlog(text: str) -> list[str]:
    """Return problems in BACKLOG.md text; empty list means valid."""
    items = parse_items(text)
    problems = _common_problems(items)
    for item in items:
        state = item.fields.get("state")
        if state not in BACKLOG_STATES:
            problems.append(f"{item.item_id}: invalid state '{state}' (allowed: {sorted(BACKLOG_STATES)})")
        gated = item.fields.get("gated")
        if gated not in GATED_VALUES:
            problems.append(f"{item.item_id}: invalid gated '{gated}' (allowed: {sorted(GATED_VALUES)})")
        if not item.fields.get("why"):
            problems.append(f"{item.item_id}: missing field 'why'")
        if not item.dod:
            problems.append(f"{item.item_id}: missing dod")
        elif not any(line.startswith("failure case:") for line in item.dod):
            problems.append(f"{item.item_id}: dod has no 'failure case:' line")
    return problems


def check_inbox(text: str) -> list[str]:
    """Return problems in INBOX.md text; empty list means valid."""
    items = parse_items(text)
    problems = _common_problems(items)
    for item in items:
        for key in INBOX_FIELDS:
            if not item.fields.get(key):
                problems.append(f"{item.item_id}: missing field '{key}'")
        state = item.fields.get("state")
        if state is not None and state not in INBOX_STATES:
            problems.append(f"{item.item_id}: invalid state '{state}' (allowed: {sorted(INBOX_STATES)})")
    return problems


def main(root: Path) -> int:
    """Check BACKLOG.md and INBOX.md under root; print problems; return exit code."""
    problems = [
        *(f"BACKLOG.md: {p}" for p in check_backlog((root / "BACKLOG.md").read_text())),
        *(f"INBOX.md: {p}" for p in check_inbox((root / "INBOX.md").read_text())),
    ]
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/company")
    sys.exit(main(target))

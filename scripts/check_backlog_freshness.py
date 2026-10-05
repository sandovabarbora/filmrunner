"""FR-132: warn when a backlog item's own note already claims it is finished
while its `state:` field has not caught up.

FR-127 sat as `state: ready` even though PR #348 and this item's own `note:`
paragraph both already said "FR-127 set to `done` -- the PR is the whole
deliverable" -- a stale `state:` line is a false "still to do" signal that
costs a future shift's one-item-per-run budget twice: once re-reading work
that is already finished, and again if it is actually re-started. A shift
caught that instance by chance while skipping the item for an unrelated
reason; this script catches the next one automatically.

Like `check_backlog_duplicates.py`, this never blocks: it only prints what
it finds. A human or a future shift still decides whether the `state:` line
was really left stale or the note is talking about something else.

Usage:
    python scripts/check_backlog_freshness.py [path/to/BACKLOG.md]
"""

from __future__ import annotations

import sys
from pathlib import Path

from check_company_docs import parse_items

# Only the phrasing a shift uses to declare *this item itself* finished --
# not any sentence that happens to contain the word "done" about a sub-task,
# a different item, or a PR that is unrelated to this one's own completion.
COMPLETION_PHRASES = (
    "set to done",
    "set to `done`",
    "the pr is the whole deliverable",
)


def stale_items(text: str) -> list[tuple[str, str]]:
    """(item_id, matched phrase) for each FR item whose own `note:` already
    claims completion while `state:` is not `done`."""
    out: list[tuple[str, str]] = []
    for item in parse_items(text):
        if not item.item_id.startswith("FR-"):
            continue
        if item.fields.get("state") == "done":
            continue
        note = item.fields.get("note", "").lower()
        for phrase in COMPLETION_PHRASES:
            if phrase in note:
                out.append((item.item_id, phrase))
                break
    return out


def format_report(stale: list[tuple[str, str]]) -> str:
    if not stale:
        return "No backlog item's own note claims completion while its state is not done."
    lines = ["Possible stale state (warning only -- a human or a future shift still decides):"]
    for item_id, phrase in stale:
        lines.append(f'  {item_id}: note contains "{phrase}" but state is not done')
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("docs/company/BACKLOG.md")
    print(format_report(stale_items(path.read_text())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

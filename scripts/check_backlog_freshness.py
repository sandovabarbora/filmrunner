"""FR-132: warn when a backlog item's own note already claims it is finished
while its `state:` field has not caught up.

FR-127 sat as `state: ready` even though PR #348 and this item's own `note:`
paragraph both already said "FR-127 set to `done` -- the PR is the whole
deliverable" -- a stale `state:` line is a false "still to do" signal that
costs a future shift's one-item-per-run budget twice: once re-reading work
that is already finished, and again if it is actually re-started. A shift
caught that instance by chance while skipping the item for an unrelated
reason; this script catches the next one automatically.

FR-176 extends the same idea to `LOG.md`: FR-175 and FR-161 both had their
completion ("FR-175 set to `done`") recorded only in `STATUS.md`/`LOG.md`,
never written back into the item's own `BACKLOG.md` note, because the shift
that finished them opened a state-only PR touching just those two files.
The original check above never sees this -- it only reads `BACKLOG.md`'s own
`note:` field -- so it printed a false "no drift" right before that gap was
found by chance. `stale_items_in_log` catches the next one automatically by
reading `LOG.md` too.

Like `check_backlog_duplicates.py`, this never blocks: it only prints what
it finds. A human or a future shift still decides whether the `state:` line
was really left stale or the note/log line is talking about something else.

Usage:
    python scripts/check_backlog_freshness.py [path/to/BACKLOG.md] [path/to/LOG.md]
"""

from __future__ import annotations

import re
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

# LOG.md is one line per shift and often names several items in passing
# (e.g. "FR-79 is done and ready for a future shift" while completing a
# different item). Anchor the match to the exact id immediately followed by
# "set to done" -- the phrasing every completed LOG.md line already uses for
# *its own* item -- so a passing mention of another id's state never matches.
def _log_completion_pattern(item_id: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(item_id)}\b\s+set\s+to\s+`?done`?", re.IGNORECASE)


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


def stale_items_in_log(backlog_text: str, log_text: str) -> list[tuple[str, str]]:
    """(item_id, phrase) for each FR item whose most recent `LOG.md` mention
    of that exact id is a completion line ("FR-<n> set to done"), while
    `BACKLOG.md`'s own `state:` for that item is not `done`.

    Only a line whose stated subject is completing *that* id matches --
    `LOG.md` is append-only, so the last match in the file is the most
    recent shift's word on it."""
    out: list[tuple[str, str]] = []
    log_lines = log_text.splitlines()
    for item in parse_items(backlog_text):
        if not item.item_id.startswith("FR-"):
            continue
        if item.fields.get("state") == "done":
            continue
        pattern = _log_completion_pattern(item.item_id)
        if any(pattern.search(line) for line in log_lines):
            out.append((item.item_id, "LOG.md: set to done"))
    return out


def format_report(
    stale: list[tuple[str, str]], stale_in_log: list[tuple[str, str]] | None = None
) -> str:
    stale_in_log = stale_in_log or []
    if not stale and not stale_in_log:
        return "No backlog item's own note claims completion while its state is not done."
    lines = ["Possible stale state (warning only -- a human or a future shift still decides):"]
    for item_id, phrase in stale:
        lines.append(f'  {item_id}: note contains "{phrase}" but state is not done')
    for item_id, phrase in stale_in_log:
        lines.append(f'  {item_id}: {phrase}, but BACKLOG.md state is not done')
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    backlog_path = Path(argv[0]) if len(argv) >= 1 else Path("docs/company/BACKLOG.md")
    log_path = Path(argv[1]) if len(argv) >= 2 else Path("docs/company/LOG.md")
    backlog_text = backlog_path.read_text()
    stale = stale_items(backlog_text)
    stale_in_log = stale_items_in_log(backlog_text, log_path.read_text()) if log_path.exists() else []
    print(format_report(stale, stale_in_log))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

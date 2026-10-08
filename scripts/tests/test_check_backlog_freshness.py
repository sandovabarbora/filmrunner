"""Tests for the backlog-freshness checker (FR-132)."""

from pathlib import Path

from check_backlog_freshness import format_report, main, stale_items

DONE_ITEM = """## FR-1 · qa · Already finished
- state: done
- gated: no
- why: x
- dod:
  - do the thing
  - failure case: y
- note: FR-1 set to done -- the PR is the whole deliverable.
"""

STALE_ITEM = """## FR-2 · qa · Left stale
- state: ready
- gated: no
- why: x
- dod:
  - do the thing
  - failure case: y
- note: FR-2 set to `done` -- the PR is the whole deliverable.
"""

SUBTASK_MENTION = """## FR-3 · tech-lead · Still in progress
- state: in-progress
- gated: no
- why: x
- dod:
  - do the thing
  - failure case: y
- note: filed FR-79 separately; FR-79 is done and ready for a future shift, the rest of this item's own work remains.
"""


def test_item_already_done_is_not_flagged() -> None:
    assert stale_items(DONE_ITEM) == []


def test_item_left_ready_with_a_completion_note_is_flagged() -> None:
    stale = stale_items(STALE_ITEM)
    assert stale == [("FR-2", "set to `done`")]


def test_note_mentioning_a_different_items_completion_is_not_flagged() -> None:
    """The failure case named in FR-132's own dod: a note mentioning "done" in
    passing about a sub-task or another item must not be flagged."""
    assert stale_items(SUBTASK_MENTION) == []


def test_format_report_is_clean_when_nothing_is_stale() -> None:
    assert format_report([]).startswith("No backlog item's own note claims completion")


def test_format_report_lists_each_stale_item() -> None:
    report = format_report([("FR-2", "set to `done`")])
    assert "FR-2" in report
    assert "warning only" in report


def test_main_never_fails_even_when_it_finds_something(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(STALE_ITEM)
    assert main([str(backlog)]) == 0


def test_real_backlog_has_no_drift() -> None:
    root = Path(__file__).resolve().parents[2] / "docs" / "company"
    stale = stale_items((root / "BACKLOG.md").read_text())
    assert stale == [], f"stale state found, needs a human look: {stale}"

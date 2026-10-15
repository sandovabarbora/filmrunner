"""Tests for the backlog-freshness checker (FR-132, extended by FR-176)."""

from pathlib import Path

from check_backlog_freshness import format_report, main, stale_items, stale_items_in_log

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

# FR-176's own failure mode: the completion note lives only in LOG.md, the
# item's own BACKLOG.md note never got a completion phrase written into it.
LOG_ONLY_COMPLETION_ITEM = """## FR-175 · tech-lead · Decide something
- state: ready
- gated: no
- why: x
- dod:
  - do the thing
  - failure case: y
- note: proposed 2026-10-15.
"""

NEVER_MENTIONED_ITEM = """## FR-180 · qa · Never touched
- state: ready
- gated: no
- why: x
- dod:
  - do the thing
  - failure case: y
- note: proposed 2026-10-15.
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


def test_log_completion_flags_item_whose_backlog_note_was_never_updated() -> None:
    log_text = "2026-10-15 13:11 · tech-lead · Took FR-175 directly. FR-175 set to `done` -- the ADR is the whole deliverable. Digest sent.\n"
    stale = stale_items_in_log(LOG_ONLY_COMPLETION_ITEM, log_text)
    assert stale == [("FR-175", "LOG.md: set to done")]


def test_log_mention_of_a_different_items_completion_is_not_flagged() -> None:
    """The failure case named in FR-176's own dod: a LOG.md line completing
    one item must not flag a different id it only mentions in passing."""
    log_text = "2026-10-09 16:11 · pm · filed FR-79 separately; FR-79 is done and ready for a future shift. FR-157 set to `done` -- the PR is the whole deliverable.\n"
    stale = stale_items_in_log(SUBTASK_MENTION, log_text)
    assert stale == []


def test_log_completion_is_not_flagged_once_backlog_state_is_done() -> None:
    stale = stale_items_in_log(DONE_ITEM, "FR-1 set to done -- the PR is the whole deliverable.\n")
    assert stale == []


def test_item_never_mentioned_in_log_is_not_flagged() -> None:
    stale = stale_items_in_log(NEVER_MENTIONED_ITEM, "2026-10-15 · qa · unrelated work entirely.\n")
    assert stale == []


def test_format_report_combines_backlog_and_log_findings() -> None:
    report = format_report([("FR-2", "set to `done`")], [("FR-175", "LOG.md: set to done")])
    assert "FR-2" in report
    assert "FR-175" in report
    assert "LOG.md: set to done" in report


def test_real_log_has_no_drift_against_real_backlog() -> None:
    root = Path(__file__).resolve().parents[2] / "docs" / "company"
    stale = stale_items_in_log(
        (root / "BACKLOG.md").read_text(), (root / "LOG.md").read_text()
    )
    assert stale == [], f"completion found only in LOG.md, needs a human look: {stale}"

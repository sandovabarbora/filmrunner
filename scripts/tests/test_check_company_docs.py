"""Tests for the company-docs format checker.

The checker is the routine's and CI's guard that BACKLOG.md and INBOX.md
stay machine-readable; these tests pin the grammar so a doc edit that
breaks it fails loudly instead of silently confusing the daily shift.
"""

from pathlib import Path

import pytest

from check_company_docs import ROLES, check_backlog, check_inbox, main

GOOD_BACKLOG = """# Backlog

## FR-1 · pm · BRIEF.md v0
- state: ready
- gated: no
- why: no constitution yet
- dod:
  - BRIEF.md lists open questions
  - failure case: a question with no owner is flagged, not dropped
"""

GOOD_INBOX = """# Inbox

## #1 · marketing · Send interview invitations
- state: pending
- what: email 5 first ADs
- why: discovery
- risk: cold outreach from an unknown sender
- proposal: founder sends from her own address
"""


def test_good_backlog_has_no_problems() -> None:
    assert check_backlog(GOOD_BACKLOG) == []


def test_good_inbox_has_no_problems() -> None:
    assert check_inbox(GOOD_INBOX) == []


def test_duplicate_backlog_id_is_reported() -> None:
    text = GOOD_BACKLOG + GOOD_BACKLOG.split("# Backlog")[1]
    problems = check_backlog(text)
    assert any("duplicate id FR-1" in p for p in problems)


def test_invalid_state_is_reported() -> None:
    text = GOOD_BACKLOG.replace("state: ready", "state: someday")
    problems = check_backlog(text)
    assert any("FR-1: invalid state 'someday'" in p for p in problems)


def test_unknown_role_is_reported() -> None:
    text = GOOD_BACKLOG.replace("· pm ·", "· ceo ·")
    problems = check_backlog(text)
    assert any("FR-1: unknown role 'ceo'" in p for p in problems)
    assert "pm" in ROLES


def test_backlog_item_without_failure_case_is_reported() -> None:
    text = GOOD_BACKLOG.replace("  - failure case: a question with no owner is flagged, not dropped\n", "")
    problems = check_backlog(text)
    assert any("FR-1: dod has no 'failure case:' line" in p for p in problems)


def test_inbox_missing_field_is_reported() -> None:
    text = GOOD_INBOX.replace("- risk: cold outreach from an unknown sender\n", "")
    problems = check_inbox(text)
    assert any("#1: missing field 'risk'" in p for p in problems)


def test_main_returns_nonzero_on_problem(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(GOOD_BACKLOG.replace("gated: no", "gated: maybe"))
    (tmp_path / "INBOX.md").write_text(GOOD_INBOX)
    assert main(tmp_path) == 1


def test_main_returns_zero_on_clean_docs(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(GOOD_BACKLOG)
    (tmp_path / "INBOX.md").write_text(GOOD_INBOX)
    assert main(tmp_path) == 0


@pytest.mark.parametrize("filename", ["BACKLOG.md", "INBOX.md"])
def test_real_company_docs_are_valid(filename: str) -> None:
    root = Path(__file__).resolve().parents[2] / "docs" / "company"
    assert (root / filename).exists(), f"{filename} missing from docs/company"
    assert main(root) == 0

"""Tests for the branch and PR-title convention checker."""

import pytest

from check_conventions import check_branch, check_title, main


@pytest.mark.parametrize(
    "branch",
    ["docs/fr-2-competitive-teardown", "chore/shift-state-2026-09-14", "feat/pdf-export", "fix/revision-z"],
)
def test_good_branches(branch: str) -> None:
    assert check_branch(branch) is None


@pytest.mark.parametrize("branch", ["shift/FR-2", "founding/main-rules", "feature/x", "docs/", "Docs/x", "main"])
def test_bad_branches(branch: str) -> None:
    assert check_branch(branch) is not None


@pytest.mark.parametrize(
    "title",
    ["docs(pm): FR-2 competitive teardown", "fix(api): reject 27th revision", "chore(state): daily shift 2026-09-14", "ci: add conventions check"],
)
def test_good_titles(title: str) -> None:
    assert check_title(title) is None


@pytest.mark.parametrize(
    "title",
    ["Update README", "docs: ends with period.", "feature(x): wrong type", "docs(PM): uppercase scope", "docs:missing space"],
)
def test_bad_titles(title: str) -> None:
    assert check_title(title) is not None


def test_main_reports_both_problems(capsys: pytest.CaptureFixture[str]) -> None:
    assert main("shift/FR-2", "Update README") == 1
    out = capsys.readouterr().out
    assert "branch 'shift/FR-2'" in out
    assert "title 'Update README'" in out


def test_main_clean() -> None:
    assert main("docs/x", "docs: x") == 0

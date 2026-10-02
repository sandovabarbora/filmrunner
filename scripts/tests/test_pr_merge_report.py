"""Tests for the PR merge-readiness report's classification logic.

`fetch_open_prs`/`main` shell out to `gh`, which this sandbox does not have installed, so
they are verified separately via a real workflow_dispatch run (see the FR-114 backlog note
and DECISIONS.md) rather than here. Everything test-able without a live `gh` call is covered.
"""

import pytest

from pr_merge_report import PullRequest, ci_conclusion, classify_bucket, flag_for_attention, format_table


@pytest.mark.parametrize(
    "files",
    [
        ["docs/company/STATUS.md"],
        ["docs/company/INBOX.md", "docs/company/LOG.md"],
        ["docs/company/BACKLOG.md"],
        ["docs/research/prague-market-sizing.md"],
        ["docs/marketing/positioning.md"],
        ["docs/gates/pre-merge-checklist.md"],
        [".github/pull_request_template.md"],
    ],
)
def test_reversible_only_is_auto_merge(files: list[str]) -> None:
    assert classify_bucket(files) == "auto-merge"


@pytest.mark.parametrize(
    "files",
    [
        ["backend/app/main.py"],
        ["frontend/src/editor/App.tsx"],
        ["scripts/check_live_stack.py"],
        [".github/workflows/ci.yml"],
        ["docs/adr/ADR-006-location-services.md"],
        ["docs/company/BRIEF.md"],
        ["docs/company/TEAM.md"],
        ["docs/company/DECISIONS.md"],
        # a mix of one reversible and one non-reversible file is founder-merge as a whole,
        # not averaged -- TEAM.md's rule reads "a PR that touches only these paths".
        ["docs/company/STATUS.md", "backend/app/main.py"],
        # a path the allowlist doesn't name is never guessed as safe.
        ["docs/ops/data-retention.md"],
        ["README.md"],
    ],
)
def test_any_non_reversible_file_is_founder_merge(files: list[str]) -> None:
    assert classify_bucket(files) == "founder-merge"


def test_no_files_is_unknown() -> None:
    assert classify_bucket([]) == "unknown"


def test_ci_conclusion_reads_the_ci_check_only() -> None:
    rollup = [
        {"name": "Claude Approvals", "conclusion": "failure"},
        {"name": "ci", "conclusion": "success"},
    ]
    assert ci_conclusion(rollup) == "success"


def test_ci_conclusion_falls_back_to_state_for_status_contexts() -> None:
    rollup = [{"context": "ci", "state": "pending"}]
    assert ci_conclusion(rollup) == "pending"


def test_ci_conclusion_unknown_when_ci_check_absent() -> None:
    assert ci_conclusion([{"name": "codeql"}]) == "unknown"


def _pr(**kwargs) -> PullRequest:
    defaults = dict(number=1, title="t", created_at="2026-01-01T00:00:00Z", mergeable_state="clean", ci="success", files=[])
    defaults.update(kwargs)
    return PullRequest(**defaults)


def test_flag_conflict_beats_everything() -> None:
    pr = _pr(mergeable_state="dirty", ci="failure")
    assert flag_for_attention(pr) == "CONFLICT"


def test_flag_ci_red() -> None:
    assert flag_for_attention(_pr(ci="failure")) == "CI RED"


def test_flag_ci_running() -> None:
    assert flag_for_attention(_pr(ci="pending")) == "CI RUNNING"


def test_flag_none_when_clean_and_green() -> None:
    assert flag_for_attention(_pr()) is None


def test_format_table_empty() -> None:
    assert format_table([]) == "No open PRs."


def test_format_table_sorts_oldest_first_and_flags_conflicts() -> None:
    old = _pr(number=1, title="old", created_at="2026-01-01T00:00:00Z")
    new = _pr(number=2, title="new", created_at="2026-02-01T00:00:00Z", mergeable_state="dirty")
    out = format_table([new, old])
    assert out.index("#1") < out.index("#2")
    assert "CONFLICT" in out.splitlines()[-1]


def test_format_table_truncates_long_titles() -> None:
    pr = _pr(title="x" * 100)
    out = format_table([pr])
    assert "x" * 61 not in out
    assert "..." in out

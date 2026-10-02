"""Tests for the FR-109 deploy-staleness decision logic in check_live_stack.py.

`deploy_matches_main`/`fetch` hit the live API and the public GitHub API, so they
are verified by a real workflow_dispatch run (same pattern as check_live_stack.py's
other live checks), not here. `deploy_staleness_message` takes its inputs already
fetched, so the decision/formatting logic is fully testable without a network call.
"""

from check_live_stack import deploy_staleness_message


def test_no_reported_sha_is_unverified_not_a_failure() -> None:
    ok, detail = deploy_staleness_message(None, "irrelevant", {})
    assert ok is True
    assert "cannot verify" in detail
    assert "predates commit reporting" in detail


def test_matching_sha_is_up_to_date() -> None:
    sha = "a" * 40
    ok, detail = deploy_staleness_message(sha, sha, {})
    assert ok is True
    assert "up to date" in detail
    assert sha[:7] in detail


def test_behind_main_reports_count_and_oldest_commit_date() -> None:
    deployed = "b" * 40
    main = "c" * 40
    compare = {
        "ahead_by": 3,
        "commits": [
            {"commit": {"committer": {"date": "2026-09-30T08:00:00Z"}}},
            {"commit": {"committer": {"date": "2026-10-01T09:00:00Z"}}},
            {"commit": {"committer": {"date": "2026-10-02T07:00:00Z"}}},
        ],
    }
    ok, detail = deploy_staleness_message(deployed, main, compare)
    assert ok is False
    assert "3 commits behind main" in detail
    assert "2026-09-30T08:00:00Z" in detail
    assert deployed[:7] in detail
    assert main[:7] in detail


def test_behind_main_with_no_commit_list_still_reports_rather_than_crashing() -> None:
    ok, detail = deploy_staleness_message("d" * 40, "e" * 40, {"ahead_by": 1, "commits": []})
    assert ok is False
    assert "1 commits behind main" in detail
    assert "since unknown" in detail

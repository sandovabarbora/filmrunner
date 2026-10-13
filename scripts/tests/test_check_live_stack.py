"""Tests for the FR-109/FR-166 decision logic in check_live_stack.py.

`deploy_matches_main`/`rate_limit_is_enforced_live`/`fetch` hit the live API and the public
GitHub API, so they are verified by a real workflow_dispatch run (same pattern as
check_live_stack.py's other live checks), not here. `deploy_staleness_message` and
`classify_rate_limit_burst` take their inputs already fetched, so the decision/formatting
logic is fully testable without a network call.
"""

from check_live_stack import classify_rate_limit_burst, deploy_staleness_message


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


def test_no_429_in_the_burst_is_a_failure() -> None:
    ok, detail = classify_rate_limit_burst([(200, {}) for _ in range(301)])
    assert ok is False
    assert "none 429'd" in detail


def test_429_without_retry_after_is_a_failure() -> None:
    results = [(200, {}) for _ in range(300)] + [(429, {})]
    ok, detail = classify_rate_limit_burst(results)
    assert ok is False
    assert "missing Retry-After" in detail


def test_429_with_retry_after_passes() -> None:
    results = [(200, {}) for _ in range(300)] + [(429, {"retry-after": "30"})]
    ok, detail = classify_rate_limit_burst(results)
    assert ok is True
    assert "1/301 requests 429'd" in detail


def test_some_429s_missing_retry_after_is_still_a_failure() -> None:
    results = [(429, {"retry-after": "30"}), (429, {})]
    ok, detail = classify_rate_limit_burst(results)
    assert ok is False
    assert "1 of those were missing Retry-After" in detail

"""Tests for the FR-109/FR-164 deploy-staleness decision logic in check_live_stack.py.

`deploy_matches_main`/`fetch` hit the live API and the public GitHub API, so they
are verified by a real workflow_dispatch run (same pattern as check_live_stack.py's
other live checks), not here. `deploy_staleness_message` takes its inputs already
fetched, so the decision/formatting logic is fully testable without a network call.

FR-164: the decision has three distinct outcomes, not two — "cannot verify" must
never collapse into the same status as a real pass, since the markdown renderer
(`MARKS`) and the job's own exit code (`main()`) both key off `status`, not an
`ok`/not-`ok` boolean.
"""

from check_live_stack import MARKS, _status, check, deploy_staleness_message


def test_no_reported_sha_is_unverified_not_ok_and_not_fail() -> None:
    status, detail = deploy_staleness_message(None, "irrelevant", {})
    assert status == "warn"
    assert "cannot verify" in detail
    assert "predates commit reporting" in detail


def test_matching_sha_is_up_to_date() -> None:
    sha = "a" * 40
    status, detail = deploy_staleness_message(sha, sha, {})
    assert status == "ok"
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
    status, detail = deploy_staleness_message(deployed, main, compare)
    assert status == "fail"
    assert "3 commits behind main" in detail
    assert "2026-09-30T08:00:00Z" in detail
    assert deployed[:7] in detail
    assert main[:7] in detail


def test_behind_main_with_no_commit_list_still_reports_rather_than_crashing() -> None:
    status, detail = deploy_staleness_message("d" * 40, "e" * 40, {"ahead_by": 1, "commits": []})
    assert status == "fail"
    assert "1 commits behind main" in detail
    assert "since unknown" in detail


def test_cannot_verify_renders_as_a_distinct_marker_not_the_pass_mark() -> None:
    status, _ = deploy_staleness_message(None, "irrelevant", {})
    assert MARKS[status] == "⚠️"
    assert MARKS[status] != MARKS["ok"]


def test_cannot_verify_does_not_count_as_a_failure_in_the_check_wrapper() -> None:
    name, status, detail = check("deploy", lambda: deploy_staleness_message(None, "irrelevant", {}))
    assert status == "warn"
    # main()'s exit code only counts "fail"; a "warn" must never be one.
    assert status != "fail"


def test_status_passthrough_accepts_bool_for_ordinary_pass_fail_checks() -> None:
    assert _status(True) == "ok"
    assert _status(False) == "fail"


def test_status_rejects_an_unknown_string() -> None:
    import pytest

    with pytest.raises(ValueError):
        _status("maybe")  # type: ignore[arg-type]

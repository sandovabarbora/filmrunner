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

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import check_live_stack
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


COMPARE = {"status": "ahead", "ahead_by": 3}


def _commit(sha: str, date: str) -> dict:
    return {"sha": sha, "commit": {"committer": {"date": date}}}


def test_behind_on_backend_reports_count_and_oldest_commit_date() -> None:
    deployed = "b" * 40
    main = "c" * 40
    newest_first = [_commit("2" * 40, "2026-10-02T07:00:00Z"), _commit("1" * 40, "2026-09-30T08:00:00Z")]
    status, detail = deploy_staleness_message(deployed, main, COMPARE, newest_first)
    assert status == "fail"
    assert "2 backend commits behind main" in detail
    assert "2026-09-30T08:00:00Z" in detail
    assert deployed[:7] in detail
    assert main[:7] in detail


def test_commits_outside_backend_do_not_make_the_deploy_stale() -> None:
    status, detail = deploy_staleness_message("d" * 40, "e" * 40, COMPARE, [])
    assert status == "ok"
    assert "3 commits ahead outside backend/" in detail


def test_the_deployed_commit_itself_is_not_counted_as_behind() -> None:
    deployed = "d" * 40
    status, _ = deploy_staleness_message(deployed, "e" * 40, COMPARE, [_commit(deployed, "2026-10-02T07:00:00Z")])
    assert status == "ok"


def test_a_deploy_from_outside_main_is_a_failure() -> None:
    status, detail = deploy_staleness_message("d" * 40, "e" * 40, {"status": "diverged"})
    assert status == "fail"
    assert "not on main" in detail


def _github_and_api(monkeypatch, responses: dict[str, tuple[int, dict]]) -> list[str]:
    asked = []

    def fake_fetch(url, headers=None):
        asked.append(url)
        for fragment, (status, body) in responses.items():
            if fragment in url:
                return status, json.dumps(body).encode(), {}
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(check_live_stack, "fetch", fake_fetch)
    return asked


def test_deploy_matches_main_asks_only_for_backend_commits_since_the_deployed_one(monkeypatch) -> None:
    deployed, main = "d" * 40, "e" * 40
    asked = _github_and_api(monkeypatch, {
        "/healthz": (200, {"git_sha": deployed}),
        "/commits/main": (200, {"sha": main}),
        "/compare/": (200, {"status": "ahead", "ahead_by": 2, "base_commit": {"commit": {"committer": {"date": "2026-11-01T00:00:00Z"}}}}),
        "/commits?": (200, []),
    })
    status, _ = check_live_stack.deploy_matches_main()
    assert status == "ok"
    listing = next(url for url in asked if "/commits?" in url)
    assert "path=backend" in listing and "since=2026-11-01T00:00:00Z" in listing and f"sha={main}" in listing


def test_readyz_absent_until_the_next_deploy_warns_rather_than_fails(monkeypatch) -> None:
    _github_and_api(monkeypatch, {"/readyz": (404, {})})
    assert check_live_stack.api_ready()[0] == "warn"


def test_readyz_503_fails_and_200_passes(monkeypatch) -> None:
    _github_and_api(monkeypatch, {"/readyz": (503, {"status": "unavailable"})})
    assert check_live_stack.api_ready()[0] == "fail"
    _github_and_api(monkeypatch, {"/readyz": (200, {"status": "ok"})})
    assert check_live_stack.api_ready()[0] == "ok"


def test_the_daily_check_runs_before_a_0500_prague_call_in_winter_and_summer() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/pilot-readiness.yml").read_text()
    minute, hour = re.search(r'cron: "(\d+) (\d+) \* \* \*"', workflow).groups()
    for day in (date(2026, 1, 15), date(2026, 7, 15)):
        utc = datetime(day.year, day.month, day.day, int(hour), int(minute), tzinfo=timezone.utc)
        prague = utc.astimezone(ZoneInfo("Europe/Prague"))
        assert prague.hour < 4, f"{prague} leaves no time for the T-1h check"


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

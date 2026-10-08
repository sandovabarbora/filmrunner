"""Tests for FR-152's finding-extraction and accept/new classification logic.

`run_pip_audit`/`run_npm_audit` shell out to real scanners, so they are
verified by a real `workflow_dispatch` run of `dependency-audit.yml` (same
pattern `check_live_stack.py`'s own tests use for its network calls), not
here. `extract_pip_finding_ids`, `extract_npm_finding_ids`, and `classify`
take already-fetched data, so the parsing/decision logic is fully testable
without a scanner or the network.
"""

from check_dependency_audit import (
    classify,
    extract_npm_finding_ids,
    extract_pip_finding_ids,
)


def test_extract_pip_finding_ids_flattens_across_dependencies() -> None:
    data = {
        "dependencies": [
            {"name": "pyjwt", "version": "2.13.0", "vulns": [{"id": "PYSEC-2026-1"}, {"id": "PYSEC-2026-2"}]},
            {"name": "fastapi", "version": "0.141.1", "vulns": []},
        ]
    }
    assert extract_pip_finding_ids(data) == ["PYSEC-2026-1", "PYSEC-2026-2"]


def test_extract_pip_finding_ids_empty_when_clean() -> None:
    assert extract_pip_finding_ids({"dependencies": [{"name": "fastapi", "vulns": []}]}) == []


def test_extract_npm_finding_ids_reads_advisory_url_not_package_name_via() -> None:
    """A real npm audit --json shape: a package's `via` can be a plain string naming
    another package in the chain (no advisory id of its own) or a dict with the
    advisory's GitHub URL. Only the dict form contributes a finding id."""
    data = {
        "vulnerabilities": {
            "xlsx": {
                "via": [
                    {"url": "https://github.com/advisories/GHSA-4r6h-8v6p-xvw6"},
                    {"url": "https://github.com/advisories/GHSA-5pgg-2g8v-p4x9"},
                ]
            },
            "some-wrapper": {"via": ["xlsx"]},
        }
    }
    assert extract_npm_finding_ids(data) == ["GHSA-4r6h-8v6p-xvw6", "GHSA-5pgg-2g8v-p4x9"]


def test_extract_npm_finding_ids_empty_when_clean() -> None:
    assert extract_npm_finding_ids({"vulnerabilities": {}}) == []


def test_classify_no_findings_is_clean() -> None:
    ok, new = classify([], frozenset())
    assert ok is True
    assert new == []


def test_classify_only_accepted_findings_is_clean() -> None:
    accepted = frozenset({"GHSA-4r6h-8v6p-xvw6", "GHSA-5pgg-2g8v-p4x9"})
    ok, new = classify(["GHSA-4r6h-8v6p-xvw6", "GHSA-5pgg-2g8v-p4x9"], accepted)
    assert ok is True
    assert new == []


def test_classify_new_finding_fails() -> None:
    ok, new = classify(["GHSA-68fv-2mgg-jv7q"], frozenset())
    assert ok is False
    assert new == ["GHSA-68fv-2mgg-jv7q"]


def test_classify_names_only_the_new_finding_not_the_accepted_ones() -> None:
    accepted = frozenset({"GHSA-4r6h-8v6p-xvw6"})
    ok, new = classify(["GHSA-4r6h-8v6p-xvw6", "GHSA-68fv-2mgg-jv7q"], accepted)
    assert ok is False
    assert new == ["GHSA-68fv-2mgg-jv7q"]

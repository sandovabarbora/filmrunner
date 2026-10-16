"""Tests for the FR-180 failure-decision logic in check_pages_cache_headers.py.

`fetch`/`discover_hashed_assets`/`sample_asset` hit the live GitHub Pages
deployment, so they are verified by a real workflow_dispatch run (same pattern
as check_live_stack.py's other live checks), not here. The decision logic that
turns a list of already-sampled results into pass/fail is pure and fully
testable without a network call, so it is pulled out of `main()` and tested
directly against `sample_asset`-shaped fixtures.
"""

from check_pages_cache_headers import decide


def _asset(url: str, *, status: int = 200, cache_control: str | None = "max-age=600") -> dict:
    samples = [{"status": status, "cache-control": cache_control, "etag": "x", "age": "0", "x-cache": None}] * 3
    cache_controls = {s["cache-control"] for s in samples}
    return {
        "url": url,
        "samples": samples,
        "cache_control_stable": len(cache_controls) == 1,
        "has_cache_control": any(s["cache-control"] for s in samples),
    }


def test_all_assets_cached_passes() -> None:
    results = [_asset("https://example.com/assets/a-123.js"), _asset("https://example.com/assets/b-456.css")]
    failed, _ = decide(results)
    assert failed is False


def test_asset_missing_cache_control_fails() -> None:
    results = [
        _asset("https://example.com/assets/a-123.js"),
        _asset("https://example.com/assets/b-456.css", cache_control=None),
    ]
    failed, detail = decide(results)
    assert failed is True
    assert "b-456.css" in detail["missing_cache_control_names"]


def test_unstable_cache_control_across_samples_fails() -> None:
    url = "https://example.com/assets/a-123.js"
    samples = [
        {"status": 200, "cache-control": "max-age=600", "etag": "x", "age": "0", "x-cache": None},
        {"status": 200, "cache-control": "no-store", "etag": "x", "age": "0", "x-cache": None},
        {"status": 200, "cache-control": "max-age=600", "etag": "x", "age": "0", "x-cache": None},
    ]
    result = {
        "url": url,
        "samples": samples,
        "cache_control_stable": len({s["cache-control"] for s in samples}) == 1,
        "has_cache_control": any(s["cache-control"] for s in samples),
    }
    failed, detail = decide([result])
    assert failed is True
    assert "a-123.js" in detail["unstable_cache_control_names"]


def test_unreachable_asset_fails_but_is_not_double_counted_as_unstable() -> None:
    results = [_asset("https://example.com/assets/a-123.js", status=404, cache_control=None)]
    failed, detail = decide(results)
    assert failed is True
    assert detail["unreachable_names"] == ["a-123.js"]
    # A consistently-unreachable asset's absence of Cache-Control is already
    # reported as unreachable, not re-flagged as a separate "missing" failure.
    assert detail["missing_cache_control_names"] == []
    assert detail["unstable_cache_control_names"] == []

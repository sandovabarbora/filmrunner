"""FR-107: unit tests for the pinned-Chromium fallback in conftest.py.

At least a dozen prior shift notes independently re-diagnosed this sandbox's
missing pinned Playwright revision (playwright==1.47.0 expects chromium-1134;
this sandbox ships a newer one) as a known, non-actionable gap, each hand-
patching `browser_type_launch_args` and reverting it before committing rather
than fixing it once. These tests exercise the pure fallback logic directly —
no real browser launch needed — including the failure case: a corrupted/
empty browsers directory must raise a clear error, not hang or time out.
"""

import pytest

from conftest import find_fallback_chromium, resolve_chromium_launch_args


def _make_build(root, revision: str) -> None:
    chrome = root / f"chromium-{revision}" / "chrome-linux" / "chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("#!/bin/sh\necho fake chrome\n")


def test_find_fallback_chromium_picks_the_highest_installed_revision(tmp_path) -> None:
    _make_build(tmp_path, "1134")  # the pinned one, deliberately absent in the real call
    _make_build(tmp_path, "1194")
    _make_build(tmp_path, "1180")
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"
    pinned.unlink()  # simulate the pinned revision being genuinely missing

    found = find_fallback_chromium(pinned)

    assert found == tmp_path / "chromium-1194" / "chrome-linux" / "chrome"


def test_find_fallback_chromium_uses_a_convenience_symlink_if_no_versioned_dir_matches(tmp_path) -> None:
    alias_target = tmp_path / "somewhere" / "chrome"
    alias_target.parent.mkdir(parents=True)
    alias_target.write_text("#!/bin/sh\necho fake chrome\n")
    (tmp_path / "chromium").symlink_to(alias_target)
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    assert find_fallback_chromium(pinned) == tmp_path / "chromium"


def test_find_fallback_chromium_returns_none_when_nothing_is_installed(tmp_path) -> None:
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    assert find_fallback_chromium(pinned) is None


def test_resolve_chromium_launch_args_prefers_the_pinned_build_when_present(tmp_path) -> None:
    _make_build(tmp_path, "1134")
    _make_build(tmp_path, "1194")  # a fallback also exists, but must never be preferred
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    args = resolve_chromium_launch_args({"slow_mo": 50}, pinned)

    assert args == {"slow_mo": 50}  # unchanged: no executable_path override, CI is unaffected


def test_resolve_chromium_launch_args_falls_back_and_forces_new_headless(tmp_path) -> None:
    _make_build(tmp_path, "1194")
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    args = resolve_chromium_launch_args({}, pinned)

    assert args["executable_path"] == str(tmp_path / "chromium-1194" / "chrome-linux" / "chrome")
    assert "--headless=new" in args["args"]


def test_resolve_chromium_launch_args_keeps_headed_mode_untouched(tmp_path) -> None:
    _make_build(tmp_path, "1194")
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    args = resolve_chromium_launch_args({"headless": False}, pinned)

    assert args["executable_path"] == str(tmp_path / "chromium-1194" / "chrome-linux" / "chrome")
    assert "args" not in args  # --headless=new would be wrong when the caller asked for headed


def test_resolve_chromium_launch_args_raises_a_clear_error_when_nothing_is_available(tmp_path) -> None:
    """The dod's own failure case: no pinned build and no fallback must fail loudly,
    naming the missing browser, rather than leaving Playwright to hang on a bad launch."""
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    with pytest.raises(RuntimeError, match="No Chromium build found") as exc_info:
        resolve_chromium_launch_args({}, pinned)

    assert str(pinned) in str(exc_info.value)


def test_resolve_chromium_launch_args_does_not_swallow_a_real_launch_failure(tmp_path) -> None:
    """Corrupting the one fallback that does exist must still surface a real failure,
    not be silently treated as 'found' just because a matching path exists."""
    stale = tmp_path / "chromium-1194" / "chrome-linux" / "chrome"
    stale.parent.mkdir(parents=True)
    stale.mkdir()  # a directory, not an executable file: glob's is_file() must reject it
    pinned = tmp_path / "chromium-1134" / "chrome-linux" / "chrome"

    with pytest.raises(RuntimeError, match="No Chromium build found"):
        resolve_chromium_launch_args({}, pinned)

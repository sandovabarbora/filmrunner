"""FR-154: drive the Czech Film Commission's Filmography page's year filter
with real headless Chromium and read the resulting filtered count from the
rendered DOM.

FR-105 (2026-09-29) read this page's body in full via a plain HTTP fetch and
found the year filter's option labels ("2026", "2025", … "1983-2003") are
static text in the raw markup with no visible count next to them — whatever
count a real click on one of them would show is populated client-side, the
same class of gap FR-90 solved for StudioBinder/Yamdu/SetHero's JS-rendered
pricing pages. This is a filter *interaction*, not a page load, so per
FR-154's own dod it needs a script of its own rather than reusing
render_pricing_pages.py's load-and-extract-text pattern unmodified: that
script renders once and extracts text, it never clicks/selects anything and
waits for a second render.

Usage (open-egress runner only; this sandbox's own proxy blocks
filmcommission.cz directly, confirmed by every FR-20/FR-88/FR-105 shift):

    python -m playwright install --with-deps chromium
    python3 scripts/render_filmography_year_filter.py

Prints a full report to stdout and $GITHUB_STEP_SUMMARY: whether a cookie
banner was dismissed, which selector strategy (if any) found and activated a
control for the target year, the full rendered visible text before and
after, and any line matching an "N entries"-shaped count in each. Reports
the exact technical reason rather than guessing if no year control could be
found or activated.
"""

import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = "https://filmcommission.cz/en/filmography/"
TIMEOUT_MS = 30_000
TARGET_YEAR = "2025"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
COOKIE_BUTTON_TEXTS = [
    "Accept all", "Accept All", "Accept", "I agree", "I Agree",
    "Souhlasím", "Rozumím", "Povolit vše", "Allow all", "Allow All",
]
# FR-155: the three control labels FR-154's own DOM dumps showed verbatim in
# the overlay's text, used to find the real markup directly instead of
# guessing a role again.
COOKIE_OVERLAY_TEXTS = ["OK. I Agree.", "Individualised settings", "Reject all"]
_ENTRIES_RE = re.compile(r"\b\d[\d,]*\s*(total\s+)?entries\b|show results\s*\(\s*\d[\d,]*\s*\)", re.IGNORECASE)

_DUMP_MATCHING_ELEMENTS_JS = """
(needle) => {
  const matches = [];
  const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT);
  let node = walker.currentNode;
  while (node) {
    const text = (node.textContent || '').trim();
    if (text && text.includes(needle)) {
      const childHasIt = Array.from(node.children).some(c => (c.textContent || '').includes(needle));
      if (!childHasIt) {
        matches.push({
          tag: node.tagName,
          role: node.getAttribute('role'),
          id: node.id,
          className: node.className,
          outerHTML: node.outerHTML.slice(0, 500),
        });
      }
    }
    node = walker.nextNode();
  }
  return matches;
}
"""


def _dump_markup_for_texts(page, texts: list[str]) -> list[str]:
    """Search every frame's real DOM for each of `texts` and report each
    match's tag/role/id/class/outerHTML directly, per FR-155's dod: read the
    real markup instead of guessing a role again."""
    lines = []
    for frame in page.frames:
        for needle in texts:
            try:
                matches = frame.evaluate(_DUMP_MATCHING_ELEMENTS_JS, needle)
            except Exception as e:  # noqa: BLE001 — a detached/cross-origin frame must not abort the whole dump
                lines.append(f"- frame {frame.url!r}, needle {needle!r}: evaluate failed: {type(e).__name__}: {e}")
                continue
            if not matches:
                lines.append(f"- frame {frame.url!r}, needle {needle!r}: no element's textContent contains this text")
                continue
            for m in matches:
                lines.append(
                    f"- frame {frame.url!r}, needle {needle!r}: "
                    f"<{m['tag']} role={m['role']!r} id={m['id']!r} class={m['className']!r}> "
                    f"{m['outerHTML']}"
                )
    return lines


def _dump_cookie_overlay_markup(page) -> list[str]:
    return _dump_markup_for_texts(page, COOKIE_OVERLAY_TEXTS)


def _to_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return lines


def _entries_lines(lines: list[str]) -> list[str]:
    return [l for l in lines if _ENTRIES_RE.search(l)]


def _dismiss_cookie_banner(page) -> str:
    for text in COOKIE_BUTTON_TEXTS:
        try:
            btn = page.get_by_role("button", name=text, exact=False)
            if btn.count() > 0:
                btn.first.click(timeout=3000)
                page.wait_for_timeout(500)
                return f"clicked a cookie-banner button matching {text!r}"
        except Exception:  # noqa: BLE001 — try every candidate text, report the first hit
            continue
    # FR-155: the real overlay control has no accessible role at all — a
    # markup dump (_dump_cookie_overlay_markup) showed "Reject all" rendered
    # as a plain <span role=None>, so a role="button" locator can never
    # match it. Fall back to a plain text locator (any element, any role)
    # and click whatever actually renders the phrase.
    for text in COOKIE_OVERLAY_TEXTS:
        try:
            loc = page.get_by_text(text, exact=False)
            if loc.count() > 0:
                loc.first.click(timeout=3000)
                page.wait_for_timeout(500)
                return f"clicked plain-text cookie-overlay control matching {text!r} (no accessible role)"
        except Exception:  # noqa: BLE001
            continue
    return "no cookie-banner control matched any known text or role (may not exist, or none was needed)"


def _open_advanced_search(page) -> str:
    """The page's visible text includes an 'Advanced search' toggle before any
    year/country/format options appear — those options may only become
    interactable once it's expanded. Best-effort; reports what happened."""
    for role in ("button", "link"):
        try:
            loc = page.get_by_role(role, name="Advanced search", exact=False)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                page.wait_for_timeout(500)
                return f"clicked role={role} 'Advanced search'"
        except Exception:  # noqa: BLE001
            continue
    try:
        loc = page.get_by_text("Advanced search", exact=False)
        if loc.count() > 0:
            loc.first.click(timeout=5000)
            page.wait_for_timeout(500)
            return "clicked plain-text 'Advanced search'"
    except Exception:  # noqa: BLE001
        pass
    return "no 'Advanced search' toggle could be found or clicked"


def _expand_year_section(page) -> str:
    """Within the Advanced search panel, 'Year of production' reads as a
    section header with no year values shown yet — likely its own
    collapsible accordion, the same pattern 'Advanced search' itself used.
    Best-effort; reports what happened."""
    for role in ("button", "link"):
        try:
            loc = page.get_by_role(role, name="Year of production", exact=False)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                page.wait_for_timeout(500)
                return f"clicked role={role} 'Year of production'"
        except Exception:  # noqa: BLE001
            continue
    try:
        loc = page.get_by_text("Year of production", exact=False)
        if loc.count() > 0:
            loc.first.click(timeout=5000)
            page.wait_for_timeout(500)
            return "clicked plain-text 'Year of production'"
    except Exception:  # noqa: BLE001
        pass
    return "no 'Year of production' toggle could be found or clicked"


def _find_and_activate_year_control(page, year: str) -> tuple[str, bool]:
    """Try several strategies to find and activate a control for `year`.

    Returns (description of what was tried/found, whether activation succeeded).
    """
    # Strategy 1: a <select> with an option whose visible text is exactly the year.
    try:
        selects = page.locator("select")
        for i in range(selects.count()):
            sel = selects.nth(i)
            options = sel.locator("option")
            for j in range(options.count()):
                opt_text = (options.nth(j).inner_text() or "").strip()
                if opt_text == year:
                    sel.select_option(label=year)
                    return f"<select> element #{i}, chose option with text {year!r}", True
    except Exception as e:  # noqa: BLE001
        pass

    # Strategy 2: an accessible role (button/link/checkbox/radio/listitem) named exactly the year.
    for role in ("button", "link", "checkbox", "radio", "listitem", "menuitem", "option", "tab"):
        try:
            loc = page.get_by_role(role, name=year, exact=True)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                return f"accessible role={role!r} named {year!r}", True
        except Exception:  # noqa: BLE001
            continue

    # Strategy 3: any element whose exact visible text is the year, clicked directly.
    try:
        loc = page.get_by_text(year, exact=True)
        n = loc.count()
        for i in range(n):
            try:
                loc.nth(i).click(timeout=3000)
                return f"plain text match #{i + 1} of {n} elements with exact text {year!r}", True
            except Exception:  # noqa: BLE001
                continue
        if n:
            return f"found {n} element(s) with exact text {year!r} but none were clickable", False
    except Exception:  # noqa: BLE001
        pass

    return f"no element (select option, accessible role, or exact text) matching {year!r} could be found", False


def main() -> int:
    report = ["# FR-154 Filmography year-filter interaction report", ""]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 1000})
        page = context.new_page()

        try:
            response = page.goto(URL, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
            status = response.status if response else 0
            try:
                page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
            except Exception:  # noqa: BLE001 — a long-lived connection never idles; DOM is parsed regardless
                pass
        except Exception as e:  # noqa: BLE001
            msg = f"FATAL: could not load {URL}: {type(e).__name__}: {e}"
            print(msg)
            report.append(msg)
            _write_summary("\n".join(report))
            context.close()
            browser.close()
            return 1

        report.append(f"- url: {URL}")
        report.append(f"- initial load status: {status}")

        cookie_note = _dismiss_cookie_banner(page)
        report.append(f"- cookie banner: {cookie_note}")

        report.append("")
        report.append("## Cookie overlay markup dump, right after the first dismissal attempt (FR-155)")
        report.append("")
        first_dump = _dump_cookie_overlay_markup(page)
        report.extend(f"{l}" for l in first_dump) if first_dump else report.append("(no frames found)")
        report.append("")

        before_lines = _to_lines(page.locator("body").inner_text(timeout=TIMEOUT_MS))
        before_entries = _entries_lines(before_lines)

        advanced_search_note = _open_advanced_search(page)
        report.append(f"- advanced search: {advanced_search_note}")

        try:
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1000)
        after_advanced_search_lines = _to_lines(page.locator("body").inner_text(timeout=TIMEOUT_MS))
        new_after_advanced_search = [l for l in after_advanced_search_lines if l not in set(before_lines)]
        report.append("")
        report.append("## Lines present after opening Advanced search but not before (does a year-filter panel appear at all?)")
        report.append("")
        report.extend(f"- {l}" for l in new_after_advanced_search) if new_after_advanced_search else report.append(
            "(no new lines — opening Advanced search did not visibly change the rendered text)"
        )
        report.append("")

        year_section_note = _expand_year_section(page)
        report.append(f"- year-of-production section: {year_section_note}")
        try:
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1000)
        after_year_section_lines = _to_lines(page.locator("body").inner_text(timeout=TIMEOUT_MS))
        new_after_year_section = [l for l in after_year_section_lines if l not in set(after_advanced_search_lines)]
        report.append("")
        report.append("## Lines present after expanding 'Year of production' but not before (do individual years appear?)")
        report.append("")
        report.extend(f"- {l}" for l in new_after_year_section) if new_after_year_section else report.append(
            "(no new lines — expanding 'Year of production' did not visibly change the rendered text)"
        )
        report.append("")

        # FR-155: the year-section toggle itself was never confirmed
        # clickable (every attempt reports "no toggle could be found or
        # clicked") — read its real markup the same way the cookie overlay's
        # was read, instead of continuing to guess role=button/link.
        report.append("## 'Year of production'/'Format' markup dump (why can the toggle not be found or clicked?)")
        report.append("")
        year_label_dump = _dump_markup_for_texts(page, ["Year of production", "Format"])
        report.extend(year_label_dump) if year_label_dump else report.append("(no frames found)")
        report.append("")

        # The cookie-consent widget on this site renders a few seconds after
        # the initial load (the first _dismiss_cookie_banner call above, run
        # right after domcontentloaded/networkidle, consistently found no
        # match) — by now it has had time to appear, and as an overlay it
        # would intercept clicks on whatever sits underneath it, which is a
        # plausible real cause of every prior run's "found but not clickable"
        # result. Dismiss it again, now that enough time has passed.
        late_cookie_note = _dismiss_cookie_banner(page)
        report.append(f"- cookie banner (second attempt, after interacting with the page): {late_cookie_note}")

        # FR-155 dod: confirm the overlay is actually gone (not in the
        # accessibility/DOM tree any more), not just that a click was
        # attempted — a stale click target would otherwise look identical
        # to a real dismissal in the report above.
        report.append("")
        report.append("## Cookie overlay markup dump, right after the second dismissal attempt (confirms whether it is actually gone)")
        report.append("")
        second_dump = _dump_cookie_overlay_markup(page)
        if second_dump:
            report.extend(second_dump)
            # "Reject all" persisting while the other two are gone would mean
            # a *different*, always-present element (e.g. a footer "Cookie
            # settings" link) also contains that phrase — checked separately
            # below rather than treated as the modal still being up.
            overlay_gone = all(
                "no element's textContent contains this text" in l
                for l in second_dump
                if "'OK. I Agree.'" in l or "'Individualised settings'" in l
            )
        else:
            report.append("(no frames found)")
            overlay_gone = True
        report.append("")
        report.append(f"- overlay (OK I Agree / Individualised settings) confirmed gone: {overlay_gone}")
        report.append("")

        strategy_desc, activated = _find_and_activate_year_control(page, TARGET_YEAR)
        report.append(f"- year-control strategy for {TARGET_YEAR!r}: {strategy_desc}")
        report.append(f"- activation succeeded: {activated}")

        if not activated:
            # FR-155: the exact-text '2025' matches found above could be the
            # listing cards' own "2025 production" labels (a different,
            # unrelated node this script's exact-text strategy 3 never
            # distinguished from a real filter control), not the "Year of
            # production" panel's own controls. Read their real markup.
            report.append("")
            report.append(f"## {TARGET_YEAR!r} exact-text match markup dump (are these the filter's own controls, or listing-card labels?)")
            report.append("")
            year_match_dump = _dump_markup_for_texts(page, [TARGET_YEAR])
            report.extend(year_match_dump) if year_match_dump else report.append("(no frames found)")
            report.append("")

        after_lines = None
        after_entries = []
        if activated:
            try:
                page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                page.wait_for_timeout(2000)
            after_lines = _to_lines(page.locator("body").inner_text(timeout=TIMEOUT_MS))
            after_entries = _entries_lines(after_lines)

        report.append("")
        report.append("## Lines matching an \"N entries\"-shaped count, before activation")
        report.append("")
        report.extend(f"- {l}" for l in before_entries) if before_entries else report.append("(none found)")

        if activated:
            report.append("")
            report.append(f"## Lines matching an \"N entries\"-shaped count, after selecting {TARGET_YEAR}")
            report.append("")
            report.extend(f"- {l}" for l in after_entries) if after_entries else report.append("(none found)")

            report.append("")
            report.append("## Lines present after but not before (what the interaction actually changed)")
            report.append("")
            before_set = set(before_lines)
            new_lines = [l for l in after_lines if l not in before_set]
            report.extend(f"- {l}" for l in new_lines[:200]) if new_lines else report.append(
                "(no new lines — the rendered text did not visibly change after activation)"
            )

        report.append("")
        report.append("## Full rendered visible text before activation")
        report.append("")
        report.append("```")
        report.append("\n".join(before_lines)[:20000])
        report.append("```")

        report.append("")
        report.append("## Full rendered visible text right after opening Advanced search (before any year-control attempt)")
        report.append("")
        report.append("```")
        report.append("\n".join(after_advanced_search_lines)[:20000])
        report.append("```")

        if activated:
            report.append("")
            report.append(f"## Full rendered visible text after selecting {TARGET_YEAR}")
            report.append("")
            report.append("```")
            report.append("\n".join(after_lines)[:20000])
            report.append("```")

        context.close()
        browser.close()

    full_report = "\n".join(report)
    print(full_report)
    _write_summary(full_report)
    return 0


def _write_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    raise SystemExit(main())

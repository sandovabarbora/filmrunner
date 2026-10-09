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
_ENTRIES_RE = re.compile(r"\b\d[\d,]*\s*(total\s+)?entries\b|show results\s*\(\s*\d[\d,]*\s*\)", re.IGNORECASE)


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
    return "no cookie-banner button matched any known text (may not exist, or none was needed)"


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

        strategy_desc, activated = _find_and_activate_year_control(page, TARGET_YEAR)
        report.append(f"- year-control strategy for {TARGET_YEAR!r}: {strategy_desc}")
        report.append(f"- activation succeeded: {activated}")

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

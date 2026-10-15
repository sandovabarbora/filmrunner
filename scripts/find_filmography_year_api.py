"""FR-173: find a documented API or query-string pattern the Czech Film
Commission Filmography page's "Year of production" filter submits to, since
FR-154/155/156/167/168/169 (2026-10-09 to 2026-10-14) exhausted every
dispatched-browser-interaction angle on the rendered combobox without ever
reaching a "Show results (N)" counter. FR-169's own failure case named the
one untried angle: "the site exposing its counts via a documented API/
query-string pattern." This script looks for that pattern three ways,
cheapest first:

1. `robots.txt`/`sitemap.xml` and the page's own static (non-JS) HTML,
   fetched with plain `requests` — a WordPress `wp-json` REST base, a
   `<form action=...>`, or a `fetch(`/`data-url` hint would show up here
   without needing a browser at all.
2. A handful of candidate query-string/path URLs, fetched the same way,
   compared against the unfiltered baseline's own "N entries" count — if
   any candidate changes the rendered count, that is the pattern.
3. Real headless Chromium with every network request logged (reusing
   FR-169's own cookie-dismissal, Advanced-search, and Year-of-production
   expand/activate steps, unchanged) in case the filter only ever submits
   via a JS `fetch`/XHR the static HTML never reveals.

Usage (open-egress runner only; this sandbox's own proxy blocks
filmcommission.cz directly, confirmed by every FR-20/FR-88/FR-105/FR-154
shift):

    pip install -r frontend/tests/requirements.txt
    python -m playwright install --with-deps chromium
    python3 scripts/find_filmography_year_api.py

Prints a full report to stdout and $GITHUB_STEP_SUMMARY.
"""

import os
import re
import sys

import requests
from playwright.sync_api import sync_playwright

BASE = "https://filmcommission.cz"
URL = f"{BASE}/en/filmography/"
TIMEOUT_S = 30
TARGET_YEAR = "2025"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
COOKIE_BUTTON_TEXTS = [
    "Accept all", "Accept All", "Accept", "I agree", "I Agree",
    "Souhlasím", "Rozumím", "Povolit vše", "Allow all", "Allow All",
]
COOKIE_OVERLAY_TEXTS = ["OK. I Agree.", "Individualised settings", "Reject all"]
_ENTRIES_RE = re.compile(r"\b\d[\d,]*\s*(total\s+)?entries\b|show results\s*\(\s*\d[\d,]*\s*\)", re.IGNORECASE)
_API_HINT_RE = re.compile(r"wp-json|/api/|ajax|graphql", re.IGNORECASE)
_CANDIDATE_URLS = [
    f"{URL}?year={TARGET_YEAR}",
    f"{URL}?rok={TARGET_YEAR}",
    f"{URL}?filmography_year={TARGET_YEAR}",
    f"{URL}?production_year={TARGET_YEAR}",
    f"{URL}{TARGET_YEAR}/",
    f"{BASE}/wp-json/",
]


def _to_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return lines


def _entries_lines(text: str) -> list[str]:
    return [l for l in _to_lines(text) if _ENTRIES_RE.search(l)]


def _static_fetch_report() -> tuple[list[str], str]:
    lines = ["## 1. Static (non-JS) fetch: robots.txt, sitemap.xml, the page's own HTML", ""]
    baseline_html = ""

    for path in ("/robots.txt", "/sitemap.xml"):
        full = BASE + path
        try:
            r = requests.get(full, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
            api_hints = sorted(set(_API_HINT_RE.findall(r.text)))
            lines.append(f"- `{full}`: HTTP {r.status_code}, {len(r.text)} bytes, API-shaped hints: {api_hints or 'none'}")
            if path == "/sitemap.xml" and "filmography" in r.text.lower():
                fm_lines = [l for l in r.text.splitlines() if "filmography" in l.lower()][:10]
                lines.append(f"  filmography-related sitemap lines (first 10): {fm_lines}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"- `{full}`: fetch failed ({type(e).__name__}: {e})")

    try:
        r = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
        baseline_html = r.text
        api_hints = sorted(set(_API_HINT_RE.findall(r.text)))
        forms = re.findall(r"<form[^>]*>", r.text, re.IGNORECASE)
        fetch_calls = re.findall(r"fetch\(\s*['\"]([^'\"]+)['\"]", r.text)
        data_urls = re.findall(r'data-(?:url|endpoint|api)=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
        baseline_entries = _entries_lines(re.sub(r"<[^>]+>", " ", r.text))
        lines.append(f"- `{URL}` (no JS executed): HTTP {r.status_code}, {len(r.text)} bytes")
        lines.append(f"  API-shaped hints in raw HTML: {api_hints or 'none'}")
        lines.append(f"  `<form>` tags found: {forms or 'none'}")
        lines.append(f"  inline `fetch(...)` call targets: {fetch_calls or 'none'}")
        lines.append(f"  `data-url`/`data-endpoint`/`data-api` attributes: {data_urls or 'none'}")
        lines.append(f"  'N entries'-shaped text in the no-JS HTML: {baseline_entries or 'none (confirms the count is JS-rendered, not in the initial HTML)'}")
    except Exception as e:  # noqa: BLE001
        lines.append(f"- `{URL}`: fetch failed ({type(e).__name__}: {e})")

    lines.append("")
    return lines, baseline_html


def _candidate_url_report(baseline_html: str) -> list[str]:
    lines = ["## 2. Candidate query-string/path URLs, fetched directly (no browser, no JS)", ""]
    baseline_len = len(baseline_html)
    for cand in _CANDIDATE_URLS:
        try:
            r = requests.get(cand, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S, allow_redirects=True)
            same_as_baseline = r.text.strip() == baseline_html.strip()
            entries = _entries_lines(re.sub(r"<[^>]+>", " ", r.text))
            lines.append(
                f"- `{cand}`: HTTP {r.status_code} (final URL `{r.url}`), {len(r.text)} bytes "
                f"({'identical to the unfiltered baseline' if same_as_baseline else f'differs from baseline ({baseline_len} bytes)'}); "
                f"'N entries' text: {entries or 'none'}"
            )
        except Exception as e:  # noqa: BLE001
            lines.append(f"- `{cand}`: fetch failed ({type(e).__name__}: {e})")
    lines.append("")
    return lines


# --- Playwright network-capture step: reuses FR-169's own working helpers
# for cookie dismissal, opening Advanced search, and expanding the Year of
# production section verbatim (confirmed to work by that run's job log),
# with every network request logged instead of only inspecting the DOM. ---

def _dismiss_cookie_banner(page) -> str:
    for text in COOKIE_BUTTON_TEXTS:
        try:
            btn = page.get_by_role("button", name=text, exact=False)
            if btn.count() > 0:
                btn.first.click(timeout=3000)
                page.wait_for_timeout(500)
                return f"clicked a cookie-banner button matching {text!r}"
        except Exception:  # noqa: BLE001
            continue
    for text in COOKIE_OVERLAY_TEXTS:
        try:
            loc = page.get_by_text(text, exact=False)
            if loc.count() > 0:
                loc.first.click(timeout=3000)
                page.wait_for_timeout(500)
                return f"clicked plain-text cookie-overlay control matching {text!r}"
        except Exception:  # noqa: BLE001
            continue
    return "no cookie-banner control matched"


def _open_advanced_search(page) -> str:
    for role in ("button", "link"):
        try:
            loc = page.get_by_role(role, name="Advanced search", exact=False)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                page.wait_for_timeout(500)
                return f"clicked role={role} 'Advanced search'"
        except Exception:  # noqa: BLE001
            continue
    return "no 'Advanced search' toggle could be found or clicked"


def _expand_year_section(page) -> str:
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


def _try_open_combobox(page) -> bool:
    combobox_loc = page.locator("xpath=//*[normalize-space(text())='Year of production']/..")
    if combobox_loc.count() == 0:
        return False
    try:
        combobox_loc.first.scroll_into_view_if_needed(timeout=5000)
        combobox_loc.first.click(timeout=5000)
        return True
    except Exception:  # noqa: BLE001
        return False


def _try_click_year(page, year: str) -> None:
    try:
        loc = page.get_by_text(year, exact=True)
        for i in range(loc.count()):
            try:
                loc.nth(i).click(timeout=3000)
                return
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass


def _network_capture_report() -> list[str]:
    lines = [
        "## 3. Real headless Chromium with every network request logged "
        "(same interaction sequence FR-169 confirmed reaches the open "
        "combobox, at its 1920x1080 viewport)",
        "",
    ]
    requests_log: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on(
            "request",
            lambda req: requests_log.append(f"{req.method} {req.url} (resource_type={req.resource_type})"),
        )

        try:
            page.goto(URL, timeout=30_000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:  # noqa: BLE001
                pass
        except Exception as e:  # noqa: BLE001
            lines.append(f"FATAL: could not load {URL}: {type(e).__name__}: {e}")
            context.close()
            browser.close()
            return lines

        cookie_note = _dismiss_cookie_banner(page)
        lines.append(f"- cookie banner: {cookie_note}")
        requests_before_search = len(requests_log)

        _open_advanced_search(page)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1000)

        _expand_year_section(page)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1000)

        requests_before_combobox = len(requests_log)
        opened = _try_open_combobox(page)
        lines.append(f"- combobox opened: {opened}")
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1000)

        requests_before_year_click = len(requests_log)
        _try_click_year(page, TARGET_YEAR)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(2000)
        requests_after_year_click = len(requests_log)

        context.close()
        browser.close()

    lines.append(f"- total requests captured: {len(requests_log)}")
    lines.append(f"- requests fired while opening Advanced search / expanding Year of production: {requests_before_combobox - requests_before_search}")
    lines.append(f"- requests fired while opening the combobox: {requests_before_year_click - requests_before_combobox}")
    lines.append(f"- requests fired after clicking {TARGET_YEAR!r}: {requests_after_year_click - requests_before_year_click}")
    lines.append("")

    new_after_year_click = requests_log[requests_before_year_click:]
    lines.append(f"### Every request fired after clicking {TARGET_YEAR!r} (THE ANSWER, if any XHR/fetch/document request appears here)")
    lines.append("")
    lines.extend(f"- {r}" for r in new_after_year_click) if new_after_year_click else lines.append(
        "(none — clicking the year fired no new network request at all, consistent with the click raising "
        "an exception before any request-triggering handler ran, as FR-169 already found)"
    )
    lines.append("")

    api_shaped = [r for r in requests_log if _API_HINT_RE.search(r) or "year" in r.lower() or "filmography" in r.lower() and "?" in r]
    lines.append("### Every captured request, across the whole run, that looks API/filter-shaped (contains an API hint, 'year', or a query string on the filmography path)")
    lines.append("")
    lines.extend(f"- {r}" for r in sorted(set(api_shaped))) if api_shaped else lines.append("(none found in any of the requests this run captured)")
    lines.append("")

    other_hosts = sorted({re.match(r"\w+ https?://([^/]+)", r).group(1) for r in requests_log if re.match(r"\w+ https?://([^/]+)", r)} - {"filmcommission.cz", "www.filmcommission.cz"})
    lines.append(f"### Distinct hosts contacted other than filmcommission.cz (a separate API/CDN host would show up here): {other_hosts or 'none'}")
    lines.append("")

    return lines


def main() -> int:
    report = ["# FR-173 Filmography year-filter API/query-string search", ""]

    static_lines, baseline_html = _static_fetch_report()
    report.extend(static_lines)
    report.extend(_candidate_url_report(baseline_html))
    report.extend(_network_capture_report())

    full_report = "\n".join(report)
    print(full_report)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(full_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

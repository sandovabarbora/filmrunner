"""FR-174 (follow-up to FR-173): extend the Czech Film Commission Filmography
page's own per-year count endpoint into a real count series, 2015-2026.

FR-173 found and confirmed the endpoint the page's Angular app calls to
render its results count:

    GET https://filmcommission.gov.cz/umbraco/surface/SearchSurface/GetFilmographyCount
        ?currentPageId=7181&filterUrl=<url-encoded path+query>

and proved it is a real server-side year filter, not a fixed fallback: a
genuinely invalid year and an unrelated query key both fall back to the same
unfiltered total, while every recognized year returns a distinct count.

This script calls the same endpoint for every year 2015 through 2026
inclusive, plus the same two control probes FR-173 used (an invalid year and
an unrelated query key) so a behaviour change mid-sweep is caught rather than
silently producing a filled-in guess. stdlib only, matches fetch_page_text.py
conventions (open egress required — GitHub Actions runners only, this
sandbox's own proxy blocks the domain).

Usage: `python3 scripts/probe_filmography_count_api.py`
Writes to $GITHUB_STEP_SUMMARY when running in Actions, and always prints to
stdout.
"""

import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"
BASE = "https://filmcommission.gov.cz/umbraco/surface/SearchSurface/GetFilmographyCount"
CURRENT_PAGE_ID = "7181"
YEARS = list(range(2015, 2027))  # 2015..2026 inclusive


def _call(filter_url: str) -> tuple[int, str, str]:
    """Returns (status_code, body, error). body is '' on error."""
    qs = urllib.parse.urlencode({"currentPageId": CURRENT_PAGE_ID, "filterUrl": filter_url})
    url = f"{BASE}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(10_000).decode("utf-8", errors="replace").strip(), ""
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return 0, "", f"{type(e).__name__}: {e}"


def main(argv: list[str]) -> int:
    report = ["# FR-174 Filmography per-year count series (2015-2026)", ""]

    # Baseline + both FR-173 control probes first, so a behaviour change
    # (e.g. the fallback value itself shifting) is visible before trusting
    # any year result below it.
    report.append("## Control probes (must match FR-173's own findings)")
    report.append("")
    controls = [
        ("baseline (no filter)", "/en/filmography/"),
        ("invalid year (abc)", "/en/filmography/?year=abc"),
        ("unrelated key (foo=bar)", "/en/filmography/?foo=bar"),
    ]
    control_results = {}
    for label, filter_url in controls:
        status, body, err = _call(filter_url)
        control_results[label] = (status, body, err)
        report.append(f"- {label}: status={status or 'unreachable'}{' (' + err + ')' if err else ''}, body=`{body}`")
    baseline_value = control_results["baseline (no filter)"][1]
    report.append("")
    fallback_consistent = (
        control_results["invalid year (abc)"][1] == baseline_value
        and control_results["unrelated key (foo=bar)"][1] == baseline_value
    )
    report.append(
        f"Fallback consistency check: {'PASS' if fallback_consistent else 'FAIL'} "
        f"— both control probes {'match' if fallback_consistent else 'do NOT match'} the baseline "
        f"(`{baseline_value}`)."
    )
    report.append("")

    report.append("## Per-year counts, 2015-2026")
    report.append("")
    report.append("| year | status | count | note |")
    report.append("|---|---|---|---|")
    rows = []
    for year in YEARS:
        status, body, err = _call(f"/en/filmography/?year={year}")
        is_fallback = body == baseline_value
        note = "FALLBACK (same as unfiltered baseline — not a real filtered count)" if is_fallback else ""
        if err:
            note = f"FETCH ERROR: {err}"
        rows.append((year, status, body, is_fallback, err))
        report.append(f"| {year} | {status or 'unreachable'} | `{body}` | {note} |")

    report.append("")
    failed = [r for r in rows if r[4] or r[3]]
    if failed:
        report.append(
            f"**{len(failed)} year(s) did not return a real filtered count** "
            "(fetch error or fell back to the unfiltered baseline) — see the table above; "
            "do not report a figure for these years."
        )
    else:
        report.append(
            "All 12 years returned a status 200 response distinct from the unfiltered baseline "
            "(or a plausible real zero) — no fallback or fetch-error years to exclude."
        )
    report.append("")

    values = [int(r[2]) for r in rows if not r[3] and not r[4] and r[2].lstrip("-").isdigit()]
    if values:
        report.append(f"Observed range across valid years: {min(values)}-{max(values)}.")

    out = "\n".join(report)
    print(out)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

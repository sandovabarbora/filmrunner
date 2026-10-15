"""FR-173 follow-up: `find_filmography_year_api.py`'s network capture found
the real AJAX endpoint the Filmography page's Angular app calls to render
its results count — an Umbraco surface controller:

    GET https://filmcommission.gov.cz/umbraco/surface/SearchSurface/GetFilmographyCount
        ?currentPageId=7181&filterUrl=%2Fen%2Ffilmography%2F

captured with the *unfiltered* `filterUrl` (the year click never completed a
real form submission, consistent with every FR-154/155/156/169 finding).
This script calls the same endpoint directly with `filterUrl` values that
encode a year filter, to see whether the endpoint itself understands one
and, if so, what the real per-year count is.

Usage (open-egress runner only): python3 scripts/probe_filmography_count_api.py
"""

import os

import requests

ENDPOINT = "https://filmcommission.gov.cz/umbraco/surface/SearchSurface/GetFilmographyCount"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://filmcommission.gov.cz/en/filmography/",
}
TIMEOUT_S = 30

CANDIDATES = [
    ("baseline, unfiltered (exact capture)", {"currentPageId": "7181", "filterUrl": "/en/filmography/"}),
    ("year as a filterUrl query param", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=2025"}),
    ("year as a filterUrl query param, encoded value", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=2025&"}),
    ("rok (Czech 'year') as a filterUrl query param", {"currentPageId": "7181", "filterUrl": "/en/filmography/?rok=2025"}),
    ("year as its own top-level param", {"currentPageId": "7181", "filterUrl": "/en/filmography/", "year": "2025"}),
    ("a different year, same pattern as the best filterUrl candidate", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=2020"}),
    ("year 1990, same pattern", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=1990"}),
    ("year 2010, same pattern", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=2010"}),
    ("year 2026, same pattern", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=2026"}),
    ("year 1950 (implausibly early, should be 0 or near-0 if real)", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=1950"}),
    ("nonsense year value 'abc' (should error or fall back if filterUrl is really parsed)", {"currentPageId": "7181", "filterUrl": "/en/filmography/?year=abc"}),
    ("nonsense query key entirely unrelated to year (does ANY query string on filterUrl trigger the same 22?)", {"currentPageId": "7181", "filterUrl": "/en/filmography/?foo=bar"}),
]


def main() -> int:
    report = ["# FR-173 GetFilmographyCount endpoint probe", ""]
    results = []
    for label, params in CANDIDATES:
        try:
            r = requests.get(ENDPOINT, params=params, headers=HEADERS, timeout=TIMEOUT_S)
            body = r.text.strip()
            results.append((label, params, r.status_code, body))
            report.append(f"- **{label}** (`{r.url}`): HTTP {r.status_code}, body: `{body[:300]}`")
        except Exception as e:  # noqa: BLE001
            report.append(f"- **{label}**: fetch failed ({type(e).__name__}: {e})")

    bodies = {body for _, _, status, body in results if status == 200}
    report.append("")
    if len(bodies) <= 1:
        report.append(
            "## Conclusion: every candidate returned the same body regardless of "
            "`filterUrl`'s query string — the endpoint does not derive its count "
            "from `filterUrl`'s own query parameters (likely only the path, or it "
            "ignores this param format entirely). No working year-filter parameter "
            "found by this probe."
        )
    else:
        report.append(
            "## Conclusion: at least one candidate's body differs from the others — "
            "a real year-filter parameter may have been found. Compare the bodies above directly."
        )

    full_report = "\n".join(report)
    print(full_report)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(full_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

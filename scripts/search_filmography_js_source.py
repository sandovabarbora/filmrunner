"""FR-167: read the Czech Film Commission Filmography page's own client-side
JS source (inline scripts plus every same-origin `<script src>` it loads)
for what sets or clears the "Year of production" `role="combobox"`
element's `display: none`.

FR-156 (2026-10-09) tried every interaction a dispatched Playwright script
can attempt (scroll-into-view, ancestor-chain dump, sibling-toggle click)
and confirmed the element's own computed style is `display: none` with no
collapsed ancestor and no identifiable sibling toggle — then named "reading
the page's own client-side JS/framework source" as the one untried angle,
explicitly outside what a rendered-page interaction script can do. This is
that: a text search over the page's actual script source, not another
rendered interaction.

Usage (open-egress runner only; this sandbox's own proxy blocks
filmcommission.cz directly, confirmed by every FR-20/FR-88/FR-105/FR-154
shift):

    python3 scripts/search_filmography_js_source.py

Prints a full report to stdout and $GITHUB_STEP_SUMMARY: every script the
page loads (same-origin fetched and searched, third-party only listed,
since the dod scopes the search to same-origin source), and every line
across the page's inline scripts plus the fetched same-origin scripts that
mentions any of the needle strings naming this control. Reports the exact
outcome rather than guessing if nothing is found.
"""

import html
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

URL = "https://filmcommission.cz/en/filmography/"
TIMEOUT = 20
MAX_SCRIPT_BYTES = 2_000_000
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"

# Needles: the visible label (FR-156's own DOM dump), the raw class tokens
# FR-155 found on the combobox itself, and the underlying field name a
# filtering library would plausibly use.
NEEDLES = [
    "Year of production",
    "year of production",
    "is-dropdown",
    "show-desktop",
    "yearOfProduction",
    "year_of_production",
    "year-of-production",
]

_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_SRC_ATTR_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _fetch(url: str, max_bytes: int = 3_000_000) -> tuple[int, str, str]:
    """Returns (status_code, body_text, error). body_text is '' on error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(max_bytes)
            return r.status, raw.decode(r.headers.get_content_charset() or "utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return 0, "", f"{type(e).__name__}: {e}"


def _find_needle_lines(label: str, text: str) -> list[str]:
    hits = []
    for i, line in enumerate(text.splitlines()):
        for needle in NEEDLES:
            if needle.lower() in line.lower():
                snippet = line.strip()
                if len(snippet) > 400:
                    idx = line.lower().find(needle.lower())
                    snippet = "…" + line[max(0, idx - 150) : idx + 250] + "…"
                hits.append(f"{label}:{i + 1}: {snippet}")
                break
    return hits


def main(argv: list[str]) -> int:
    report: list[str] = ["# FR-167 Filmography page JS-source search", "", f"Target: {URL}", ""]
    all_hits: list[str] = []

    status, body, err = _fetch(URL)
    report.append(f"## Page fetch — status: {status or 'unreachable'}{' — ' + err if err else ''} ({len(body)} bytes)")
    report.append("")
    if status != 200:
        report.append("Page itself is not reachable from this runner — same egress block as every prior FR-20/FR-88/FR-105/FR-154 shift hit, or a new failure. Stopping here per this item's own failure case.")
        print("\n".join(report))
        _write_summary("\n".join(report))
        return 1

    page_origin = urllib.parse.urlparse(URL)
    same_site = page_origin.netloc.lower().lstrip("www.")

    script_tags = _SCRIPT_TAG_RE.findall(body)
    same_origin_srcs: list[str] = []
    third_party_srcs: list[str] = []
    inline_bodies: list[str] = []

    for attrs, inline_body in script_tags:
        src_match = _SRC_ATTR_RE.search(attrs)
        if src_match:
            resolved = urllib.parse.urljoin(URL, html.unescape(src_match.group(1)))
            netloc = urllib.parse.urlparse(resolved).netloc.lower().lstrip("www.")
            if netloc == same_site or netloc.endswith("." + same_site):
                same_origin_srcs.append(resolved)
            else:
                third_party_srcs.append(resolved)
        elif inline_body.strip():
            inline_bodies.append(inline_body)

    report.append(f"## Scripts found: {len(same_origin_srcs)} same-origin (`{same_site}`), "
                   f"{len(third_party_srcs)} third-party, {len(inline_bodies)} inline block(s)")
    report.append("")
    report.append("### Same-origin `<script src>`")
    for s in same_origin_srcs:
        report.append(f"- {s}")
    if not same_origin_srcs:
        report.append("(none)")
    report.append("")
    report.append("### Third-party `<script src>` (NOT fetched — dod scopes the search to same-origin source)")
    for s in third_party_srcs:
        report.append(f"- {s}")
    if not third_party_srcs:
        report.append("(none)")
    report.append("")

    for i, inline in enumerate(inline_bodies):
        all_hits.extend(_find_needle_lines(f"inline-script-{i}", inline))

    report.append("### Same-origin script fetch results")
    report.append("")
    for src in same_origin_srcs:
        s_status, s_body, s_err = _fetch(src, MAX_SCRIPT_BYTES)
        report.append(f"- `{src}` — status: {s_status or 'unreachable'}{' — ' + s_err if s_err else ''} ({len(s_body)} bytes)")
        if s_status == 200:
            all_hits.extend(_find_needle_lines(src, s_body))

    report.append("")
    report.append(f"## Needle matches across inline scripts + same-origin script source ({len(all_hits)} total)")
    report.append("")
    report.append(f"Needles searched: {', '.join(NEEDLES)}")
    report.append("")
    if all_hits:
        for h in all_hits:
            report.append(f"- {h}")
    else:
        report.append("(none — no needle string appears anywhere in the page's inline scripts or its "
                       "same-origin script source)")

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
    raise SystemExit(main(sys.argv))

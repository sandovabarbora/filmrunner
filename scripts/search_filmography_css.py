"""FR-168: fetch the Czech Film Commission Filmography page's own same-origin
stylesheet(s) (plus inline `<style>` blocks) and search the combined CSS text
for the `.show-desktop` selector FR-155 found on the "Year of production"
combobox, reporting the exact rule and, if the selector sits inside an
`@media` block, the breakpoint it requires.

FR-167 (2026-10-13) searched the page's full JS source (inline scripts plus
every same-origin `<script src>`, 908KB combined) and found no
control-specific flag anywhere — the only match was a generic, page-wide
`.is-dropdown` click handler that toggles a CSS class and never sets
`display` itself. It named the combobox's `show-desktop` class as "shaped
exactly like a responsive-visibility utility class, which would be a CSS
`@media` rule, not JS" and explicitly out of that item's own scope (script
source only). This is that: a text search over stylesheet source, not
script source, and not another rendered interaction (FR-156 already
exhausted the interaction-script angle).

Usage (open-egress runner only; this sandbox's own proxy blocks
filmcommission.cz directly, confirmed by every FR-20/FR-88/FR-105/FR-154/
FR-167 shift):

    python3 scripts/search_filmography_css.py

Prints a full report to stdout and $GITHUB_STEP_SUMMARY: every stylesheet
the page loads (same-origin fetched and searched, third-party only listed),
every inline `<style>` block, and every occurrence of `.show-desktop` found
across that combined text together with its enclosing rule and any `@media`
context it sits inside. Reports the exact outcome rather than guessing if
nothing is found.
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
MAX_CSS_BYTES = 2_000_000
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"

NEEDLE = ".show-desktop"

_LINK_TAG_RE = re.compile(r"<link\b([^>]*)>", re.IGNORECASE)
_REL_ATTR_RE = re.compile(r"""\brel\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_HREF_ATTR_RE = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)


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


def _find_rule_contexts(label: str, css: str) -> list[str]:
    """Walks `css` tracking a stack of enclosing blocks (rule selector or
    `@media` prelude). Each time the needle appears inside a selector/prelude
    that is about to open a new block, or inside a declaration, records the
    full context stack at that point. Brace-naive (does not special-case
    strings containing braces) — acceptable for a research read, not a CSS
    parser.
    """
    hits: list[str] = []
    stack: list[str] = []
    i = 0
    n = len(css)
    buf_start = 0
    while i < n:
        ch = css[i]
        if ch == "{":
            prelude = css[buf_start:i].strip()
            prelude_one_line = re.sub(r"\s+", " ", prelude)
            if NEEDLE.lower() in prelude_one_line.lower():
                context = " > ".join(stack) if stack else "(top level)"
                hits.append(f"{label}: selector `{prelude_one_line[:200]}` inside [{context}]")
            stack.append(prelude_one_line[:150] if prelude_one_line else "(anonymous block)")
            buf_start = i + 1
        elif ch == "}":
            # a declaration block's body can itself contain the needle only
            # inside a `content: "..."` string in practice; still scan it so
            # nothing is silently skipped.
            body = css[buf_start:i]
            if NEEDLE.lower() in body.lower():
                context = " > ".join(stack) if stack else "(top level)"
                hits.append(f"{label}: found inside declaration body under [{context}] (not a selector)")
            if stack:
                stack.pop()
            buf_start = i + 1
        i += 1
    # anything left in the final buffer (top-level text after the last '}')
    tail = css[buf_start:]
    if NEEDLE.lower() in tail.lower():
        hits.append(f"{label}: found in trailing top-level text")
    return hits


def main(argv: list[str]) -> int:
    report: list[str] = ["# FR-168 Filmography page CSS search", "", f"Target: {URL}", f"Needle: `{NEEDLE}`", ""]
    all_hits: list[str] = []

    status, body, err = _fetch(URL)
    report.append(f"## Page fetch — status: {status or 'unreachable'}{' — ' + err if err else ''} ({len(body)} bytes)")
    report.append("")
    if status != 200:
        report.append("Page itself is not reachable from this runner — same egress block as every prior "
                       "FR-20/FR-88/FR-105/FR-154/FR-167 shift hit, or a new failure. Stopping here per "
                       "this item's own failure case.")
        print("\n".join(report))
        _write_summary("\n".join(report))
        return 1

    page_origin = urllib.parse.urlparse(URL)
    same_site = page_origin.netloc.lower().lstrip("www.")

    same_origin_hrefs: list[str] = []
    third_party_hrefs: list[str] = []
    for attrs in _LINK_TAG_RE.findall(body):
        rel_match = _REL_ATTR_RE.search(attrs)
        href_match = _HREF_ATTR_RE.search(attrs)
        if not href_match:
            continue
        rel = (rel_match.group(1).lower() if rel_match else "")
        if "stylesheet" not in rel:
            continue
        resolved = urllib.parse.urljoin(URL, html.unescape(href_match.group(1)))
        netloc = urllib.parse.urlparse(resolved).netloc.lower().lstrip("www.")
        if netloc == same_site or netloc.endswith("." + same_site):
            same_origin_hrefs.append(resolved)
        else:
            third_party_hrefs.append(resolved)

    inline_style_blocks = _STYLE_TAG_RE.findall(body)

    report.append(f"## Stylesheets found: {len(same_origin_hrefs)} same-origin (`{same_site}`), "
                   f"{len(third_party_hrefs)} third-party, {len(inline_style_blocks)} inline `<style>` block(s)")
    report.append("")
    report.append("### Same-origin `<link rel=stylesheet href>`")
    for s in same_origin_hrefs:
        report.append(f"- {s}")
    if not same_origin_hrefs:
        report.append("(none)")
    report.append("")
    report.append("### Third-party `<link rel=stylesheet href>` (NOT fetched — same-origin scope, same precedent as FR-167's JS search)")
    for s in third_party_hrefs:
        report.append(f"- {s}")
    if not third_party_hrefs:
        report.append("(none)")
    report.append("")

    for i, inline_css in enumerate(inline_style_blocks):
        all_hits.extend(_find_rule_contexts(f"inline-style-{i}", html.unescape(inline_css)))

    report.append("### Same-origin stylesheet fetch results")
    report.append("")
    fetched_any = False
    truncated_any = False
    for href in same_origin_hrefs:
        s_status, s_body, s_err = _fetch(href, MAX_CSS_BYTES)
        report.append(f"- `{href}` — status: {s_status or 'unreachable'}{' — ' + s_err if s_err else ''} ({len(s_body)} bytes)")
        if s_status == 200:
            fetched_any = True
            if len(s_body) >= MAX_CSS_BYTES:
                truncated_any = True
            all_hits.extend(_find_rule_contexts(href, s_body))

    report.append("")
    report.append(f"## `.show-desktop` matches across inline styles + same-origin stylesheet source ({len(all_hits)} total)")
    report.append("")
    if all_hits:
        for h in all_hits:
            report.append(f"- {h}")
    elif not fetched_any and not inline_style_blocks:
        report.append("(no stylesheet or inline style block was fetchable — see failure case)")
    else:
        report.append(f"(none — `{NEEDLE}` does not appear anywhere in the page's inline styles or its "
                       "fetched same-origin stylesheet source)")

    if truncated_any:
        report.append("")
        report.append(f"**Note:** at least one stylesheet hit the {MAX_CSS_BYTES}-byte read cap and may be "
                       "truncated — a match past that point would be missed.")

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

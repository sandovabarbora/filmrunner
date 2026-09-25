"""FR-88: read a page's actual body text from a runner with open egress,
instead of the substring-match approach `reverify_desk_research.py` uses.

FR-83 confirmed `filmcommission.cz/en/statistics/` is reachable from GitHub
Actions (this sandbox's own proxy still rejects it), but its own
substring-check pattern only proves the page loaded — it does not surface
what number the page actually states, since a real count could be phrased
any number of ways ("142 productions in 2025", "142 filming permits issued",
a table with no surrounding sentence at all). Guessing a checklist of
substrings for a page nobody here has read is exactly the guessing this
company's docs are supposed to avoid.

This script instead strips the page down to plain, line-broken text and
prints every line that contains a digit, plus the full text, so a human (or
the shift reading this job's log) can read the real sentence or table row
around any figure directly — no keyword list to get wrong.

Usage: `python3 scripts/fetch_page_text.py <url> [<url> ...]` (stdlib only).
Writes to $GITHUB_STEP_SUMMARY when running in Actions, and always prints to
stdout.
"""

import html
import os
import re
import sys
import urllib.error
import urllib.request

TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"

# Tags whose closing marks the end of a visual block; we insert a newline
# there so the stripped text roughly follows the page's own line/paragraph
# structure instead of becoming one run-on line.
_BLOCK_CLOSE_RE = re.compile(r"</(p|div|li|h[1-6]|tr|section|article|br)\s*>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_DIGIT_LINE_RE = re.compile(r"\d")


def _fetch(url: str) -> tuple[int, str, str]:
    """Returns (status_code, body_text, error). body_text is '' on error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(3_000_000)
            return r.status, raw.decode(r.headers.get_content_charset() or "utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return 0, "", f"{type(e).__name__}: {e}"


def _to_lines(body: str) -> list[str]:
    body = _SCRIPT_STYLE_RE.sub(" ", body)
    body = _BR_RE.sub("\n", body)
    body = _BLOCK_CLOSE_RE.sub("\n", body)
    body = _TAG_RE.sub(" ", body)
    body = html.unescape(body)
    lines = []
    for raw_line in body.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return lines


def main(argv: list[str]) -> int:
    urls = argv[1:]
    if not urls:
        print("usage: fetch_page_text.py <url> [<url> ...]", file=sys.stderr)
        return 2

    report_parts = ["# FR-88 page text dump", ""]
    for url in urls:
        status, body, err = _fetch(url)
        report_parts.append(f"## {url}")
        report_parts.append(f"- status: {status or 'unreachable'}{' — ' + err if err else ''} ({len(body)} bytes)")
        if status == 200:
            lines = _to_lines(body)
            digit_lines = [l for l in lines if _DIGIT_LINE_RE.search(l)]
            report_parts.append(f"- {len(lines)} text lines, {len(digit_lines)} contain a digit")
            report_parts.append("")
            report_parts.append("### Lines containing a digit (candidate figures)")
            report_parts.append("")
            if digit_lines:
                for l in digit_lines:
                    report_parts.append(f"- {l}")
            else:
                report_parts.append("(none found)")
            report_parts.append("")
            report_parts.append("### Full stripped text")
            report_parts.append("")
            report_parts.append("```")
            report_parts.append("\n".join(lines)[:20000])
            report_parts.append("```")
        report_parts.append("")

    report = "\n".join(report_parts)
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

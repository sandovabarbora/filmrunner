"""FR-159: retry the SetHero Wayback Machine lookup FR-158 could not complete.

FR-158's CDX search for `sethero.com/pricing/` (a full-history, digest-
collapsed query against `web.archive.org/cdx/search/cdx`) timed out on
every attempt across two separate dispatches (1x20s, then 3x45s) and never
returned a snapshot list either way — a genuinely different, still-open
outcome from "checked and exhausted" (Yamdu's own CDX lookup completed and
read a real snapshot that simply carried no pricing text).

This script retries with the Internet Archive's lightweight availability
endpoint (`archive.org/wayback/available`), which returns only the single
closest snapshot and never collapses full crawl history the way the CDX
search does — the likely source of the earlier timeout.

Usage (from a runner with open egress; this sandbox's own proxy blocks
`archive.org`/`web.archive.org` directly, the same class of block FR-158
and others hit on other domains): `python3 scripts/fetch_wayback_sethero_retry.py`
(stdlib only). Writes to $GITHUB_STEP_SUMMARY when running in Actions, and
always prints to stdout.
"""

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 45
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"
TARGET_URL = "sethero.com/pricing/"

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_CLOSE_RE = re.compile(r"</(p|div|li|h[1-6]|tr|section|article|br)\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_DIGIT_LINE_RE = re.compile(r"\d")


def _availability_lookup(url: str) -> tuple[str | None, str | None, str]:
    """Returns (timestamp, original_snapshot_url, error) via the lightweight
    availability endpoint — a single closest-match lookup, no CDX history
    collapse."""
    api_url = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(200_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return None, None, f"availability HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return None, None, f"availability {type(e).__name__}: {e}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, None, f"availability returned non-JSON: {e}"

    closest = (data.get("archived_snapshots") or {}).get("closest")
    if not closest or not closest.get("available"):
        return None, None, "no snapshot found (availability endpoint)"
    return closest.get("timestamp"), closest.get("url"), ""


def _fetch_snapshot(url: str, timestamp: str) -> tuple[int, str, str]:
    """Returns (status_code, body_text, error). body_text is '' on error.
    Uses the id_ modifier so the raw archived page comes back, not the
    Wayback toolbar/link-rewritten version."""
    snapshot_url = f"https://web.archive.org/web/{timestamp}id_/{url}"
    req = urllib.request.Request(snapshot_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(3_000_000)
            return r.status, raw.decode(r.headers.get_content_charset() or "utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
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


def main() -> int:
    report_parts = ["# FR-159 SetHero Wayback Machine retry (availability endpoint)", ""]
    report_parts.append(f"- live url: {TARGET_URL}")

    timestamp, snapshot_url, err = _availability_lookup(TARGET_URL)
    if timestamp is None:
        report_parts.append(f"- availability lookup: {err}")
        report_parts.append("")
        print("\n".join(report_parts))
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("\n".join(report_parts))
        return 0

    report_parts.append(f"- availability lookup: snapshot found, timestamp {timestamp}")
    report_parts.append(f"- availability endpoint's own url: {snapshot_url}")
    id_url = f"https://web.archive.org/web/{timestamp}id_/{TARGET_URL}"
    report_parts.append(f"- raw (id_) snapshot url: {id_url}")

    status, body, fetch_err = _fetch_snapshot(TARGET_URL, timestamp)
    report_parts.append(f"- fetch status: {status or 'unreachable'}{' — ' + fetch_err if fetch_err else ''} ({len(body)} bytes)")
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
    raise SystemExit(main())

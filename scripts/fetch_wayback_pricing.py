"""FR-158: check the Wayback Machine for archived snapshots of the two
pricing pages four separate live-page/headless-render attempts (FR-83,
FR-90, FR-148, FR-149) could never get a price figure out of — `yamdu.com/
en/pricing/` and `sethero.com/pricing/` both fully load but inject their
pricing text client-side after the initial render, and every one of those
four attempts (plain fetch, headless Chromium, twice re-confirmed) saw the
page's chrome (nav/footer) but never the figure itself. `web.archive.org`
is a genuinely different source never tried: an older crawl may predate
whatever client-side injection now hides the figure, or may have captured
the page after its own JS had already run.

This script queries the Internet Archive's CDX API for each URL, picks the
single most recent snapshot with a 200 status, fetches that snapshot's raw
content (the `id_` modifier suppresses the Wayback toolbar/link-rewriting so
the text below is the archived page's own, not the Wayback UI's), and
reports the same "strip to text, surface every line with a digit" view
`fetch_page_text.py` already uses for a plain fetch.

Usage (from a runner with open egress; this sandbox's own proxy blocks
`web.archive.org` directly, the same class of block FR-20/88/105 hit on
other domains): `python3 scripts/fetch_wayback_pricing.py` (stdlib only).
Writes to $GITHUB_STEP_SUMMARY when running in Actions, and always prints
to stdout.
"""

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 45
CDX_RETRIES = 3  # the CDX API's own search endpoint is slower and flakier
# than a single page fetch (FR-158's first dispatch timed out on SetHero's
# lookup, with no result either way) — retry a timeout a few times before
# treating it as a real "could not check" outcome.
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_CLOSE_RE = re.compile(r"</(p|div|li|h[1-6]|tr|section|article|br)\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_DIGIT_LINE_RE = re.compile(r"\d")

TARGETS = [
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "yamdu-pricing-wayback",
        "claim": "Yamdu: Flex from $45/month + $22/additional user; Core $265/month for up to 20 users — unverified, live/rendered page carries no pricing text (FR-83, FR-90, FR-135)",
        "url": "yamdu.com/en/pricing/",
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "sethero-pricing-wayback",
        "claim": "SetHero: per-project pricing and monthly subscriptions starting at $19/month — unverified, reachable but no matching figure on the live/rendered page (FR-90, FR-149)",
        "url": "sethero.com/pricing/",
    },
]


def _cdx_lookup(url: str) -> tuple[str | None, str]:
    """Returns (most_recent_200_timestamp_or_None, error)."""
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx?url="
        + urllib.parse.quote(url, safe="")
        + "&output=json&filter=statuscode:200&collapse=digest"
    )
    req = urllib.request.Request(cdx_url, headers={"User-Agent": USER_AGENT})

    raw = None
    last_err = ""
    for attempt in range(CDX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(1_000_000).decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as e:
            last_err = f"CDX HTTP {e.code}"
            break  # an HTTP error is not a timeout; retrying won't help
        except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
            last_err = f"CDX {type(e).__name__}: {e} (attempt {attempt + 1}/{CDX_RETRIES})"
    if raw is None:
        return None, last_err

    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"CDX returned non-JSON: {e}"

    if len(rows) <= 1:  # first row is the header ["urlkey","timestamp",...]
        return None, "no snapshot found"

    header = rows[0]
    ts_index = header.index("timestamp")
    timestamps = [row[ts_index] for row in rows[1:]]
    return max(timestamps), ""


def _fetch_snapshot(url: str, timestamp: str) -> tuple[int, str, str]:
    """Returns (status_code, body_text, error). body_text is '' on error."""
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
    report_parts = ["# FR-158 Wayback Machine pricing-page dump", ""]
    for target in TARGETS:
        report_parts.append(f"## {target['id']} ({target['doc']})")
        report_parts.append(f"- claim: {target['claim']}")
        report_parts.append(f"- live url: {target['url']}")

        timestamp, cdx_err = _cdx_lookup(target["url"])
        if timestamp is None:
            report_parts.append(f"- CDX lookup: {cdx_err}")
            report_parts.append("")
            continue

        report_parts.append(f"- most recent 200 snapshot: {timestamp}")
        snapshot_url = f"https://web.archive.org/web/{timestamp}id_/{target['url']}"
        report_parts.append(f"- snapshot url: {snapshot_url}")

        status, body, err = _fetch_snapshot(target["url"], timestamp)
        report_parts.append(f"- fetch status: {status or 'unreachable'}{' — ' + err if err else ''} ({len(body)} bytes)")
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

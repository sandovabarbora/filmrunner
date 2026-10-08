"""FR-90: render the client-rendered vendor pages FR-83's re-verification
pass (2026-09-24) found reachable but unreadable by a plain HTTP fetch —
`reverify_desk_research.py`'s stdlib `urllib` fetch gets the raw HTML before
the page's own JavaScript has run, so a React/Intercom app's actual pricing
or article text never appears in the response body.

This script instead drives real headless Chromium (Playwright, the same
pinned version `frontend/tests/requirements.txt` already uses for the E2E
suite) against each URL, waits for the network to go idle so client-side
rendering has finished, then extracts the page's own rendered visible text —
the same "strip to text, surface every line with a digit" approach
`fetch_page_text.py` uses for a plain fetch, applied here to a fully
rendered DOM instead of raw HTML.

Named targets (FR-83's own re-verification pass, this item's `why`):
StudioBinder pricing, Yamdu pricing (both `docs/research/competitive-teardown.md`),
and SetHero's Exporting Data article (`docs/research/switching-cost-teardown.md`).
SetHero's own pricing/FAQ pages are included too, opportunistically: FR-83
found them 403ing even from GitHub's open-egress runner (real bot protection,
not a proxy artifact) — a real browser request may or may not fare
differently, so this script reports whatever actually happens rather than
skipping them.

Usage (from a runner with open egress; this repo's own sandbox proxy blocks
every one of these vendor domains, confirmed by every FR-2/FR-83 shift):

    python -m playwright install --with-deps chromium
    python3 scripts/render_pricing_pages.py

Writes a per-page report to $GITHUB_STEP_SUMMARY when running in Actions,
and always prints the same detail to stdout. A page that still exposes
nothing useful after rendering (behind a login wall, blocked outright, or
timed out) is reported as such with the specific reason — never guessed.
"""

import os
import re
import sys

from playwright.sync_api import sync_playwright

TIMEOUT_MS = 30_000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_DIGIT_LINE_RE = re.compile(r"\d")

TARGETS = [
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "studiobinder-pricing",
        "claim": "StudioBinder: paid tiers from ~$29/seat/month, core call-sheet access free on every tier",
        "url": "https://app.studiobinder.com/pricing",
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "yamdu-pricing",
        "claim": "Yamdu: Flex from $45/month + $22/additional user; Core $265/month for up to 20 users",
        "url": "https://yamdu.com/en/pricing/",
    },
    {
        "doc": "docs/research/switching-cost-teardown.md",
        "id": "sethero-export-data",
        "claim": "SetHero: Exporting Data article names people/cast/crew/scenes/locations lists; call-sheet templates and revision history not named — unverified whether those export",
        "url": "https://help.sethero.com/en/articles/1513672-exporting-data",
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "sethero-pricing",
        "claim": "SetHero: per-project pricing and monthly subscriptions starting at $19/month",
        "url": "https://sethero.com/pricing/",
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "sethero-offline",
        "claim": "SetHero: browser-only, no app download required; offline behaviour unaddressed in earlier snippets",
        "url": "https://sethero.com/faq/",
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "studiobinder-mobile-offline",
        "claim": "StudioBinder: offline version described by a third-party review as 'in the pipeline' (not offline-capable today); unverified directly against StudioBinder's own docs because the FAQ article timed out on every plain-fetch attempt (FR-83)",
        "url": "https://support.studiobinder.com/en/articles/1065638-is-there-a-mobile-or-tablet-app-available",
    },
]


def _to_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return lines


def _render(page, url: str) -> tuple[int, str, str]:
    """Returns (status, visible_text, error). visible_text is '' on error."""
    try:
        response = page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        except Exception:
            pass  # a page with a long-lived connection (chat widgets) never
            # goes idle; the DOM is already parsed and rendered by this point.
        status = response.status if response else 0
        body_text = page.locator("body").inner_text(timeout=TIMEOUT_MS)
        return status, body_text, ""
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return 0, "", f"{type(e).__name__}: {e}"


def main() -> int:
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        for target in TARGETS:
            status, body_text, err = _render(page, target["url"])
            lines = _to_lines(body_text) if body_text else []
            digit_lines = [l for l in lines if _DIGIT_LINE_RE.search(l)]
            results.append({**target, "status": status, "error": err, "lines": lines, "digit_lines": digit_lines})
        context.close()
        browser.close()

    report_parts = ["# FR-90 rendered-pricing-page dump", ""]
    for r in results:
        report_parts.append(f"## {r['id']} ({r['doc']})")
        report_parts.append(f"- claim: {r['claim']}")
        report_parts.append(f"- url: {r['url']}")
        reachable = r["status"] == 200
        report_parts.append(
            f"- status: {r['status'] or 'unreachable'}{' — ' + r['error'] if r['error'] else ''} "
            f"({len(r['lines'])} rendered text lines)"
        )
        if reachable:
            report_parts.append(f"- {len(r['digit_lines'])} lines contain a digit")
            report_parts.append("")
            report_parts.append("### Lines containing a digit (candidate figures)")
            report_parts.append("")
            if r["digit_lines"]:
                for l in r["digit_lines"]:
                    report_parts.append(f"- {l}")
            else:
                report_parts.append("(none found)")
            report_parts.append("")
            report_parts.append("### Full rendered visible text")
            report_parts.append("")
            report_parts.append("```")
            report_parts.append("\n".join(r["lines"])[:20000])
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

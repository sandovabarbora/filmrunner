"""FR-83: re-verify FR-2/FR-20/FR-21 desk-research claims marked "unverified"
by fetching the specific vendor/public-data pages those docs already cite as
blocked, from a runner with open egress (this sandbox's own proxy rejects
every one of these domains, confirmed again on every FR-2/FR-20/FR-21 shift).

Each entry below is one claim already written into a research doc, with the
exact URL that doc names as unreachable and a short list of substrings whose
presence would confirm or update the claim. This script does not decide
confirmed/contradicted/still-unreachable on its own — matching text is a
starting point, not a verdict, since page wording varies — it fetches each
page once, reports HTTP status and byte length, and prints whether each
substring was found plus a short excerpt around the first hit, so a human (or
the shift that reads this job's summary) can update the doc's own wording
precisely instead of guessing from a search snippet.

Usage: `python3 scripts/reverify_desk_research.py` (stdlib only, no
dependencies beyond what every other check_*.py script here already uses).
Writes a per-claim table to $GITHUB_STEP_SUMMARY when running in Actions,
and always prints the same detail to stdout.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"

CLAIMS = [
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "studiobinder-pricing",
        "claim": "StudioBinder: paid tiers from ~$29/seat/month, core call-sheet access free on every tier",
        "url": "https://app.studiobinder.com/pricing",
        "checks": ["$29", "Free", "seat", "/month", "/mo"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "studiobinder-offline",
        "claim": "StudioBinder: no dedicated offline/mobile app; recipients view a web page (connectivity assumed)",
        "url": "https://support.studiobinder.com/en/articles/1065638-is-there-a-mobile-or-tablet-app-available",
        "checks": ["offline", "mobile", "app", "browser"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "yamdu-pricing",
        "claim": "Yamdu: Flex from $45/month + $22/additional user; Core $265/month for up to 20 users",
        "url": "https://yamdu.com/en/pricing/",
        "checks": ["Flex", "Core", "$45", "$265", "/month"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "sethero-pricing",
        "claim": "SetHero: per-project pricing and monthly subscriptions starting at $19/month",
        "url": "https://sethero.com/pricing/",
        "checks": ["$19", "/month", "per project", "per-project"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "sethero-offline",
        "claim": "SetHero: browser-only, no app download required; offline behaviour unaddressed in earlier snippets",
        "url": "https://sethero.com/faq/",
        "checks": ["offline", "app", "browser", "download"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "croogloo-features",
        "claim": "Croogloo: revision history / script-sides comparison feature detail (call-sheet-specific revision UI was unverified)",
        "url": "https://croogloo.com/features/",
        "checks": ["revision", "version", "history", "compare"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "movie-magic-pricing-monthly",
        "claim": "Movie Magic Scheduling: $42.99/month per seat (per a third-party aggregator, not ep.com directly)",
        "url": "https://www.ep.com/ep-store/movie-magic-scheduling-monthly/",
        "checks": ["$42", "$43", "/month", "price"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "movie-magic-pricing-annual",
        "claim": "Movie Magic Scheduling: annual pricing option (not previously checked at all)",
        "url": "https://www.ep.com/ep-store/movie-magic-scheduling-annual/",
        "checks": ["annual", "$", "/year", "save"],
    },
    {
        "doc": "docs/research/switching-cost-teardown.md",
        "id": "yamdu-capterra-reviews",
        "claim": "Yamdu: Capterra reviews describe re-entering cast/crew per production on lower tiers instead of carrying contacts forward",
        "url": "https://www.capterra.com/p/186025/Yamdu/reviews/",
        "checks": ["contact", "tier", "re-enter", "carry"],
    },
    {
        "doc": "docs/research/switching-cost-teardown.md",
        "id": "sethero-export-data",
        "claim": "SetHero: Exporting Data article names people/cast/crew/scenes/locations lists; call-sheet templates and revision history not named — unverified whether those export",
        "url": "https://help.sethero.com/en/articles/1513672-exporting-data",
        "checks": ["template", "revision", "export", "call sheet"],
    },
    {
        "doc": "docs/research/switching-cost-teardown.md",
        "id": "movie-magic-file-docs",
        "claim": "Movie Magic Scheduling's own file-format docs (neutral source, vs. the earlier competitor-page framing of 'locked in')",
        "url": "https://mms-docs.ep.com/ScheduleFiles/MovieMagicSchedulingFiles.html",
        "checks": ["MMSX", "MMS10", "proprietary", "format"],
    },
    {
        "doc": "docs/research/prague-market-sizing.md",
        "id": "czech-film-commission-stats",
        "claim": "Czech Film Commission's own statistics page — the single most likely authoritative source for a Prague production count",
        "url": "https://filmcommission.cz/en/statistics/",
        "checks": ["production", "2025", "2026", "statistic"],
    },
    {
        "doc": "docs/research/prague-market-sizing.md",
        "id": "productionlist-prague",
        "claim": "productionlist.com Prague listing: 20 productions in its database (exact date range unverified)",
        "url": "https://productionlist.com/production-location/prague-czech-republic",
        "checks": ["Prague", "production", "20"],
    },
    {
        "doc": "docs/research/prague-market-sizing.md",
        "id": "productionlist-prague-www",
        "claim": "FR-87 probe: does the www-prefixed host (search results only ever show www.productionlist.com) resolve where the bare domain 404s?",
        "url": "https://www.productionlist.com/production-location/prague-czech-republic",
        "checks": ["Prague", "production", "20"],
    },
    {
        "doc": "docs/research/competitive-teardown.md",
        "id": "croogloo-features-www",
        "claim": "FR-87 probe: does the www-prefixed host resolve where the bare croogloo.com/features/ 404s?",
        "url": "https://www.croogloo.com/features/",
        "checks": ["revision", "version", "history", "compare"],
    },
    {
        "doc": "docs/research/prague-market-sizing.md",
        "id": "diffusion-of-innovations",
        "claim": "15-20% adoption reaches critical mass for word-of-mouth spread (Rogers, via a marketing-textbook paraphrase, not the primary text)",
        "url": "https://en.wikipedia.org/wiki/Diffusion_of_innovations",
        "checks": ["early adopters", "critical mass", "13.5%", "34%", "16%"],
    },
]


def _fetch(url: str) -> tuple[int, str, str]:
    """Returns (status_code, body_text, error). body_text is '' on error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(2_000_000)
            return r.status, raw.decode(r.headers.get_content_charset() or "utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return 0, "", f"{type(e).__name__}: {e}"


def _excerpt(body: str, needle: str, width: int = 90) -> str:
    idx = body.lower().find(needle.lower())
    if idx == -1:
        return ""
    start = max(0, idx - width // 2)
    end = min(len(body), idx + len(needle) + width // 2)
    text = re.sub(r"\s+", " ", body[start:end]).strip()
    return text


def main() -> int:
    results = []
    for claim in CLAIMS:
        status, body, err = _fetch(claim["url"])
        found = {}
        for check in claim["checks"]:
            excerpt = _excerpt(body, check) if body else ""
            found[check] = excerpt
        results.append({**claim, "status": status, "byte_len": len(body), "error": err, "found": found})

    lines = ["# FR-83 desk-research re-verification", ""]
    for r in results:
        reachable = r["status"] == 200
        lines.append(f"## {r['id']} ({r['doc']})")
        lines.append(f"- claim: {r['claim']}")
        lines.append(f"- url: {r['url']}")
        lines.append(f"- status: {r['status'] or 'unreachable'}{' — ' + r['error'] if r['error'] else ''} ({r['byte_len']} bytes)")
        if reachable:
            any_hit = False
            for check, excerpt in r["found"].items():
                if excerpt:
                    any_hit = True
                    lines.append(f"  - MATCH `{check}`: …{excerpt}…")
            if not any_hit:
                lines.append("  - no listed substring matched; page reachable but claim needs manual re-reading")
        lines.append("")

    report = "\n".join(lines)
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(report)

    out_json = os.path.join(os.path.dirname(__file__), "..", "docs", "research", "desk-research-reverify.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

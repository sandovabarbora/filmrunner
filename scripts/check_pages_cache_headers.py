"""FR-85: does the real GitHub Pages deployment send cache headers for hashed static assets?

A local static-file server used during prior shifts' verification passes (Python's
`http.server`, Vite's own preview server without extra config) does not send
`Cache-Control` by default, which could make "no caching" look like a real gap when it
is actually just an artifact of how those checks were run. GitHub Pages sits behind
GitHub's own CDN and may already send different headers than a local dev server does.
This routine's own sandbox proxy blocks `sandovabarbora.github.io` (confirmed by every
FR-8/FR-16/FR-40/FR-66 attempt), so this runs from `.github/workflows/pilot-readiness.yml`
on a GitHub Actions runner instead, the same open-egress pattern FR-66/67/68/83 used.

Fetches the live page once to discover its actual hashed asset URLs (the hash changes
every build, so nothing here can be hardcoded), then fetches each asset a few times to
tell a real, stable header apart from CDN edge-cache warm-up variance, per the item's
own failure case.

Locally: `PAGES=https://sandovabarbora.github.io/filmrunner python3 scripts/check_pages_cache_headers.py`
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

PAGES = os.environ.get("PAGES", "https://sandovabarbora.github.io/filmrunner").rstrip("/")
# The browser resolves a root-relative asset path (e.g. Vite's "/filmrunner/assets/...")
# against the origin, not against PAGES itself — PAGES already carries the project path.
PAGES_ORIGIN = "://".join(PAGES.split("://")[:1] + [PAGES.split("://", 1)[1].split("/", 1)[0]])
TIMEOUT = 20
SAMPLES_PER_ASSET = 3
# Vite's default hashed-asset output: assets/<name>-<8-or-more-hex-chars>.<ext>
ASSET_RE = re.compile(r'(?:src|href)="([^"]*/assets/[^"]+\.(?:js|css))"')


def fetch(url: str) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "filmrunner-cache-header-check"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}


def discover_hashed_assets(entry_pages: list[str]) -> list[str]:
    urls: set[str] = set()
    for page in entry_pages:
        status, body, _ = fetch(f"{PAGES}/{page}" if page else PAGES)
        if status != 200:
            continue
        text = body.decode("utf-8", "replace")
        for match in ASSET_RE.findall(text):
            if match.startswith("http"):
                url = match
            elif match.startswith("/"):
                url = f"{PAGES_ORIGIN}{match}"
            else:
                url = f"{PAGES}/{match}"
            urls.add(url)
    return sorted(urls)


def sample_asset(url: str) -> dict:
    samples = []
    for _ in range(SAMPLES_PER_ASSET):
        status, _, headers = fetch(url)
        samples.append({
            "status": status,
            "cache-control": headers.get("cache-control"),
            "etag": headers.get("etag"),
            "age": headers.get("age"),
            "x-cache": headers.get("x-cache") or headers.get("x-github-request-id"),
        })
    cache_controls = {s["cache-control"] for s in samples}
    return {
        "url": url,
        "samples": samples,
        "cache_control_stable": len(cache_controls) == 1,
        "has_cache_control": any(s["cache-control"] for s in samples),
    }


def decide(results: list[dict]) -> tuple[bool, dict]:
    """Pure decision logic: which of these already-sampled assets should fail the job.

    An asset that is unreachable is reported only as unreachable — its necessarily
    absent Cache-Control is not re-flagged as a separate "missing" failure.
    """
    unreachable = [r for r in results if not all(s["status"] == 200 for s in r["samples"])]
    reachable = [r for r in results if r not in unreachable]
    missing_cache_control = [r for r in reachable if not r["has_cache_control"]]
    # Only a real flip matters: an asset that is consistently absent Cache-Control
    # is already caught by missing_cache_control above, not flagged unstable too.
    unstable_cache_control = [
        r for r in reachable if r["has_cache_control"] and not r["cache_control_stable"]
    ]
    failed = bool(unreachable or missing_cache_control or unstable_cache_control)
    detail = {
        "unreachable_names": [r["url"].rsplit("/", 1)[-1] for r in unreachable],
        "missing_cache_control_names": [r["url"].rsplit("/", 1)[-1] for r in missing_cache_control],
        "unstable_cache_control_names": [r["url"].rsplit("/", 1)[-1] for r in unstable_cache_control],
    }
    return failed, detail


def main() -> int:
    try:
        assets = discover_hashed_assets(["", "editor.html", "landing.html"])
    except Exception as exc:  # noqa: BLE001 — never a silent "not verified"
        report = (
            "## Pages cache headers (FR-85) — FAILED\n\n"
            f"Could not reach {PAGES}: {exc.__class__.__name__}: {exc}\n"
        )
        print(report)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(report)
        return 1

    if not assets:
        report = (
            "## Pages cache headers (FR-85) — FAILED\n\n"
            f"No hashed asset URLs found in {PAGES}'s HTML entry points; "
            "cannot check what was never linked.\n"
        )
        print(report)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(report)
        return 1

    results = [sample_asset(url) for url in assets[:5]]
    failed, detail = decide(results)

    heading = (
        f"## Pages cache headers (FR-85) — {'FAILED' if failed else 'OK'}, "
        f"{len(results)} hashed asset(s), {SAMPLES_PER_ASSET} fetches each"
    )
    lines = [heading, ""]
    if detail["missing_cache_control_names"]:
        lines.append(f"Missing `Cache-Control` entirely: {', '.join(detail['missing_cache_control_names'])}")
    if detail["unstable_cache_control_names"]:
        lines.append(
            "`Cache-Control` flipped across samples (not CDN warm-up, a real asset "
            f"answering 200 every time): {', '.join(detail['unstable_cache_control_names'])}"
        )
    if detail["missing_cache_control_names"] or detail["unstable_cache_control_names"]:
        lines.append("")
    lines += [
        f"`{PAGES}`",
        "",
        "| Asset | Cache-Control (stable?) | ETag present | Samples |",
        "|---|---|---|---|",
    ]
    for r in results:
        cc_values = sorted({s["cache-control"] or "(none)" for s in r["samples"]})
        cc_display = cc_values[0] if len(cc_values) == 1 else " / ".join(cc_values)
        etag_present = any(s["etag"] for s in r["samples"])
        name = r["url"].rsplit("/", 1)[-1]
        lines.append(
            f"| `{name}` | `{cc_display}` ({'stable' if r['cache_control_stable'] else 'VARIED'}) "
            f"| {'yes' if etag_present else 'no'} | {r['samples']} |"
        )
    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)

    out = {"pages": PAGES, "results": results}
    with open("docs/research/pages-cache-headers.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""FR-67: is the in-process sunrise/sunset formula actually accurate?

ADR-006 flagged `backend/app/services/astronomy.py`'s NOAA/Astronomical-
Almanac formula as accurate to "roughly ±1-2 minutes" from general
knowledge only — this routine's own egress proxy has blocked every
attempt (2026-09-15 through 2026-09-22) to check it against a live
source. Run by `.github/workflows/pilot-readiness.yml` from a GitHub
Actions runner, which has open egress this routine's sandbox does not.

Reference provider: sunrise-sunset.org's free JSON API
(https://sunrise-sunset.org/api, terms https://sunrise-sunset.org/terms —
confirmed via WebSearch 2026-09-22 since WebFetch/curl to the domain
itself are also blocked from this sandbox): no key or account, free for
reasonable request volume, answers 429 with Retry-After if abused, and
requires attribution to sunrise-sunset.org wherever its data is shown —
this comment and the job summary line below are that attribution; the
product itself never calls this API, only this one-off verification
script does. Eight requests total (sunrise + sunset for four dates) is
far under any reasonable volume, so no date-range batching is needed.

Locally (needs a real network path to api.sunrise-sunset.org, which this
sandbox's own egress proxy blocks):
    PYTHONPATH=backend python3 scripts/check_astronomy_accuracy.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services.astronomy import sunrise_sunset  # noqa: E402

LAT, LNG = 50.0755, 14.4378  # Prague, matches backend/tests/test_astronomy.py
TZ = ZoneInfo("Europe/Prague")
TOLERANCE_MINUTES = 3  # dod's starting tolerance; tighten once a real run's deviations are known
TIMEOUT = 20

# Both solstices and both equinoxes for 2026 — the same dates
# backend/tests/test_astronomy.py already checks self-consistency against.
DATES = [
    ("spring equinox", date(2026, 3, 20)),
    ("summer solstice", date(2026, 6, 21)),
    ("autumn equinox", date(2026, 9, 23)),
    ("winter solstice", date(2026, 12, 21)),
]


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def fetch_reference(on_date: date) -> tuple[str, str]:
    """Live sunrise/sunset for Prague as local HH:MM, converted the same
    way astronomy.py converts its own UTC result (zoneinfo, so DST is
    handled correctly on both sides of the comparison)."""
    url = (
        "https://api.sunrise-sunset.org/json"
        f"?lat={LAT}&lng={LNG}&date={on_date.isoformat()}&formatted=0"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "filmrunner-astronomy-check/1.0 (+https://github.com/sandovabarbora/filmrunner)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"sunrise-sunset.org HTTP {exc.code}: {exc.read()[:200]!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"sunrise-sunset.org unreachable: {exc.reason}") from exc

    data = json.loads(body)
    if data.get("status") != "OK":
        raise RuntimeError(f"sunrise-sunset.org returned status {data.get('status')!r}: {data}")
    results = data["results"]

    def to_local(iso_utc: str) -> str:
        return datetime.fromisoformat(iso_utc).astimezone(TZ).strftime("%H:%M")

    return to_local(results["sunrise"]), to_local(results["sunset"])


def main() -> int:
    rows: list[tuple[str, str, bool]] = []
    failed = False

    for label, on_date in DATES:
        computed_rise, computed_set = sunrise_sunset(LAT, LNG, on_date)
        if computed_rise is None or computed_set is None:
            rows.append((f"{label} ({on_date})", "astronomy.py returned no sunrise/sunset", False))
            failed = True
            continue
        try:
            ref_rise, ref_set = fetch_reference(on_date)
        except Exception as exc:  # noqa: BLE001 — never a silent pass, always named and failed
            rows.append((f"{label} ({on_date})", f"reference fetch failed: {exc}", False))
            failed = True
            continue

        for kind, computed, reference in (
            ("sunrise", computed_rise, ref_rise),
            ("sunset", computed_set, ref_set),
        ):
            deviation = abs(_minutes(computed) - _minutes(reference))
            ok = deviation <= TOLERANCE_MINUTES
            failed = failed or not ok
            rows.append((
                f"{label} ({on_date}) {kind}",
                f"computed {computed}, reference {reference}, deviation {deviation} min (±{TOLERANCE_MINUTES} allowed)",
                ok,
            ))

    lines = [
        f"## Astronomy accuracy — {'all within tolerance' if not failed else 'FAILING'}",
        "",
        f"Prague ({LAT}, {LNG}) vs. sunrise-sunset.org, tolerance ±{TOLERANCE_MINUTES} min · checked {date.today().isoformat()}",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for name, detail, ok in rows:
        lines.append(f"| {name} | {'✅' if ok else '❌'} | `{detail}` |")
    lines.append("")
    lines.append("Data: [sunrise-sunset.org](https://sunrise-sunset.org/api) (attribution required by its terms).")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

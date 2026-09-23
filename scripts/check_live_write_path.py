"""FR-68: live write-path check for the five features never exercised against the deployed API.

`scripts/check_live_stack.py` (FR-66) proves the deployed stack is reachable, but every one of
its checks is read-only against public endpoints. Five features have sat on "NOT VERIFIED
against the live API" in `docs/research/pilot-readiness-2026-09.md` since the pass that named
them (FR-40, "Third pass, 16:00 shift 2026-09-21") because none of them can be exercised without
creating a production and publishing a revision: deleting a location (FR-38), weather
auto-filling on publish (FR-39), the crew's "tomorrow at a glance" (FR-42), the AD's days list at
a glance (FR-43), and the personal-calls picker's precedence (FR-44). This script creates one
disposable "CI check <uuid>" production on the live stack and drives all five through the real
API end to end, then leaves the production in place (there is no delete-production endpoint;
disposability is by name only, the same convention `docs/research/pilot-readiness-live3.py` and
`backend/app/seed_demo.py` already use).

Modelled on `docs/research/pilot-readiness-live3.py` (disposable-production convention, the
shared "service" bearer token), but reads that token from the environment rather than a local
file, and reports the same way `check_live_stack.py` does, so a guarded CI step can run it:

    FILMRUNNER_CI_TOKEN=<token> python3 scripts/check_live_write_path.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from typing import Any, Callable

API = os.environ.get("API", "https://filmrunner-api.fly.dev").rstrip("/")
TOKEN = os.environ.get("FILMRUNNER_CI_TOKEN", "")
TIMEOUT = 20

Result = tuple[str, bool, str]


class TokenRejected(Exception):
    """The token was presented but the API would not accept it (401): rotated, revoked, or
    never valid. Reported as skipped, not failed — a credential problem is not a stack bug."""


def call(method: str, path: str, body: Any = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        method=method,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def check(name: str, fn: Callable[[], tuple[bool, str]]) -> Result:
    """Any exception is a failure with its text — never a silent 'not verified'."""
    try:
        ok, detail = fn()
    except Exception as exc:  # noqa: BLE001
        return name, False, f"{exc.__class__.__name__}: {exc}"
    return name, ok, detail


class Fixture:
    """One disposable production with a geocoded location, a crew member with a standing call
    time, and a published day — everything the checks below read or mutate."""

    def build(self) -> None:
        self.name = f"CI check {uuid.uuid4().hex[:8]}"
        self.shoot_date = (date.today() + timedelta(days=3)).isoformat()  # inside FR-39's 16-day forecast horizon

        status, body = call("POST", "/api/v1/productions", {"name": self.name})
        if status == 401:
            raise TokenRejected(f"create production: {status} {body}")
        if status != 201:
            raise RuntimeError(f"create production: {status} {body}")
        self.production_id = body["id"]

        status, body = call(
            "POST",
            f"/api/v1/productions/{self.production_id}/locations",
            {"name": "Riverbank, Troja", "address": "Trojská 1, Praha 7", "geo_lat": 50.1147, "geo_lng": 14.4238},
        )
        if status != 201:
            raise RuntimeError(f"create location: {status} {body}")
        self.location_id = body["id"]

        status, body = call("POST", "/api/v1/contacts", {"name": "CI Crew Member", "phone": "777123456"})
        if status != 201:
            raise RuntimeError(f"create contact: {status} {body}")
        contact_id = body["id"]

        status, body = call(
            "POST",
            f"/api/v1/productions/{self.production_id}/crew-members",
            {"contact_id": contact_id, "department": "Electric", "position": "Gaffer", "standard_call_time": "06:00"},
        )
        if status != 201:
            raise RuntimeError(f"create crew member: {status} {body}")
        self.crew_member_id = body["id"]
        self.personal_token = body["personal_token"]

        status, body = call(
            "POST",
            f"/api/v1/productions/{self.production_id}/call-sheets",
            {
                "shoot_date": self.shoot_date,
                "day_number": 1,
                "day_count": 1,
                "initial_revision": {
                    "general_crew_call": "06:30",
                    "schedule_items": [
                        {
                            "order_index": 1,
                            "scene_number": "1",
                            "int_ext": "EXT",
                            "day_night": "DAY",
                            "set_description": "Riverbank",
                            "page_count_eighths": 8,
                            "location_id": self.location_id,
                        }
                    ],
                    "crew_calls": [
                        {
                            "crew_member_id": self.crew_member_id,
                            "call_time": "05:15",
                            "pickup_time": "04:45",
                            "note": "generator first",
                        }
                    ],
                },
            },
        )
        if status != 201:
            raise RuntimeError(f"publish REV A: {status} {body}")
        self.call_sheet_id = body["id"]
        self.rev_a_weather = body["current_revision"]["weather_forecast"]


F = Fixture()


def _publish_next_revision(*, weather_forecast: str | None, location_id: str | None) -> tuple[int, Any]:
    """A later revision that never resends crew_calls, so FR-44's copy-forward rule is exercised
    the same way an AD who only touches the schedule actually publishes."""
    schedule_item = {
        "order_index": 1,
        "scene_number": "1",
        "int_ext": "EXT",
        "day_night": "DAY",
        "set_description": "Riverbank",
        "page_count_eighths": 8,
        "location_id": location_id,
    }
    body: dict[str, Any] = {"general_crew_call": "06:30", "schedule_items": [schedule_item]}
    if weather_forecast is not None:
        body["weather_forecast"] = weather_forecast
    return call("POST", f"/api/v1/call-sheets/{F.call_sheet_id}/revisions", body)


def fr44_day_entry_beats_standing_time() -> tuple[bool, str]:
    status, body = call("GET", f"/api/v1/public/call-sheets/{F.call_sheet_id}/me/{F.personal_token}")
    if status != 200:
        return False, f"{status} {body}"
    ok = body.get("personal_call") == "05:15" and body.get("pickup_time") == "04:45" and body.get("note") == "generator first"
    return ok, f"personal_call={body.get('personal_call')!r} pickup={body.get('pickup_time')!r} note={body.get('note')!r}"


def fr39_blank_weather_autofills() -> tuple[bool, str]:
    return bool(F.rev_a_weather), f"REV A weather_forecast={F.rev_a_weather!r}"


def fr39_typed_weather_not_overwritten() -> tuple[bool, str]:
    typed = "Hand-typed: clear, 4°C"
    status, body = _publish_next_revision(weather_forecast=typed, location_id=F.location_id)
    if status != 201:
        return False, f"publish REV B: {status} {body}"
    return body.get("weather_forecast") == typed, f"{status} weather_forecast={body.get('weather_forecast')!r}"


def fr38_delete_clears_schedule_items() -> tuple[bool, str]:
    status, _ = call("DELETE", f"/api/v1/productions/{F.production_id}/locations/{F.location_id}")
    if status != 204:
        return False, f"delete: {status}"
    status, body = call("GET", f"/api/v1/call-sheets/{F.call_sheet_id}")
    if status != 200:
        return False, f"reread: {status} {body}"
    items = body["current_revision"]["schedule_items"]
    ok = len(items) == 1 and items[0]["location_id"] is None and items[0]["set_description"] == "Riverbank"
    return ok, f"schedule_items={items}"


def fr38_deleted_location_not_listed() -> tuple[bool, str]:
    status, body = call("GET", f"/api/v1/productions/{F.production_id}/locations")
    if status != 200:
        return False, f"{status} {body}"
    ok = all(loc["id"] != F.location_id for loc in body)
    return ok, f"{len(body)} location(s) left"


def fr38_day_still_publishes_without_the_location() -> tuple[bool, str]:
    status, body = _publish_next_revision(weather_forecast=None, location_id=None)
    return status == 201, f"{status} {body}"


def fr44_entry_copies_forward_across_revisions() -> tuple[bool, str]:
    status, body = call("GET", f"/api/v1/public/call-sheets/{F.call_sheet_id}/me/{F.personal_token}")
    return status == 200 and body.get("personal_call") == "05:15", f"{status} personal_call={body.get('personal_call')!r}"


def fr42_next_lists_the_published_day() -> tuple[bool, str]:
    status, body = call("GET", f"/api/v1/public/crew/{F.personal_token}/next")
    if status != 200:
        return False, f"{status} {body}"
    days = body.get("days", [])
    ok = (
        len(days) == 1
        and days[0]["shoot_date"] == F.shoot_date
        and days[0]["general_crew_call"] == "06:30"
        and days[0]["first_location_name"] in (None, "Riverbank, Troja")
    )
    return ok, f"days={days}"


def fr42_unknown_token_refused() -> tuple[bool, str]:
    status, _ = call("GET", "/api/v1/public/crew/definitely-not-a-token/next")
    return status == 404, str(status)


def fr43_days_list_carries_opened_count() -> tuple[bool, str]:
    status, _ = call("POST", f"/api/v1/public/call-sheets/{F.call_sheet_id}/seen/{F.personal_token}")
    if status not in (200, 201, 204):
        return False, f"seen: {status}"
    status, body = call("GET", f"/api/v1/productions/{F.production_id}/call-sheets")
    if status != 200:
        return False, f"{status} {body}"
    day = next((d for d in body if d["id"] == F.call_sheet_id), None)
    if day is None:
        return False, "call sheet missing from the production's days list"
    opened = day.get("opened")
    ok = opened is not None and opened.get("seen") == 1 and opened.get("total") == 1
    return ok, f"opened={opened}"


def fr43_public_read_never_carries_opened() -> tuple[bool, str]:
    status, body = call("GET", f"/api/v1/public/call-sheets/{F.call_sheet_id}")
    return status == 200 and body.get("opened") is None, f"{status} opened={body.get('opened')}"


CHECKS: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
    ("FR-44: a per-day entry beats the crew member's standing call time", fr44_day_entry_beats_standing_time),
    ("FR-39: blank weather auto-fills from the forecast provider on publish", fr39_blank_weather_autofills),
    ("FR-39: a typed weather value is never overwritten on a later publish", fr39_typed_weather_not_overwritten),
    ("FR-38: deleting a location clears location_id on the day's schedule items", fr38_delete_clears_schedule_items),
    ("FR-38: the deleted location is gone from the locations list", fr38_deleted_location_not_listed),
    ("FR-38: the day still publishes with the location gone", fr38_day_still_publishes_without_the_location),
    ("FR-44: the entry copies forward to a revision that resent no crew_calls", fr44_entry_copies_forward_across_revisions),
    ("FR-42: /crew/{token}/next lists the shoot day with its call and location", fr42_next_lists_the_published_day),
    ("FR-42: an unknown personal token is refused", fr42_unknown_token_refused),
    ("FR-43: the days list carries the opened count after a real /seen hit", fr43_days_list_carries_opened_count),
    ("FR-43: the public single-sheet read never carries opened", fr43_public_read_never_carries_opened),
]


def main() -> int:
    if not TOKEN:
        print("FILMRUNNER_CI_TOKEN is not set; nothing to check.", file=sys.stderr)
        return 1

    try:
        F.build()
    except TokenRejected as exc:
        # A rotated or revoked FILMRUNNER_CI_TOKEN reads as "not run", never a false red build.
        report = f"## Live write-path checks (FR-68) — skipped: token rejected\n\n`{exc}`"
        print(report)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(report + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        results: list[Result] = [
            ("fixture: create a disposable production, location, crew member and REV A", False, f"{exc.__class__.__name__}: {exc}")
        ]
    else:
        results = [check(name, fn) for name, fn in CHECKS]

    failed = [r for r in results if not r[1]]
    lines = [
        f"## Live write-path checks (FR-68) — {'all good' if not failed else f'{len(failed)} failing'}",
        "",
        f"API `{API}` · production `{getattr(F, 'name', 'not created')}`",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for name, ok, detail in results:
        lines.append(f"| {name} | {'✅' if ok else '❌'} | `{detail}` |")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

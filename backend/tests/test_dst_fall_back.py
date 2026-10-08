"""FR-133: regression test for the three Prague wall-clock-to-UTC call
sites across the 2026-10-25 fall-back DST transition (clocks go from
03:00 CEST back to 02:00 CET) — `pilot_metrics.call_at`,
`astronomy.sunrise_sunset`, and the public "next day" endpoint's own
`datetime.now(ZoneInfo("Europe/Prague")).date()` cutoff
(`app/routers/call_sheets.py`). Each must track the real UTC+2 -> UTC+1
change rather than assume a fixed offset for the whole day; the spring
transition (2026-03-29) already has coverage in `test_astronomy.py`.
"""

import datetime as _dt
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.astronomy import sunrise_sunset
from scripts import pilot_metrics

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
PRAGUE = ZoneInfo("Europe/Prague")
PRAGUE_LAT, PRAGUE_LNG = 50.0755, 14.4378


# --- pilot_metrics.call_at ---------------------------------------------

@pytest.mark.parametrize(
    "on, hhmm, expected_utc",
    [
        (date(2026, 10, 24), "06:30", datetime(2026, 10, 24, 4, 30)),  # last CEST day, +2
        (date(2026, 10, 25), "01:00", datetime(2026, 10, 24, 23, 0)),  # before the 03:00 fall-back, still +2
        (date(2026, 10, 25), "04:00", datetime(2026, 10, 25, 3, 0)),  # after the fall-back, now +1
        (date(2026, 10, 26), "06:30", datetime(2026, 10, 26, 5, 30)),  # first full CET day, +1
    ],
)
def test_call_at_tracks_the_fall_back_not_a_fixed_offset(on: date, hhmm: str, expected_utc: datetime) -> None:
    assert pilot_metrics.call_at(on, hhmm) == expected_utc


def test_call_at_resolves_the_wall_clock_hour_that_occurs_twice() -> None:
    """02:00-03:00 on 2026-10-25 happens twice (once CEST, once CET).
    `call_at` builds its local time with the default fold (0), so it
    resolves to the first (CEST, +2) occurrence — pinned here so a change
    to how the ambiguity is resolved is a visible, reviewed decision."""
    ambiguous = pilot_metrics.call_at(date(2026, 10, 25), "02:30")
    assert ambiguous == datetime(2026, 10, 25, 0, 30)  # CEST, +2

    # The zone itself is genuinely ambiguous at that wall-clock hour: the
    # second (CET, +1) occurrence is a real, different UTC instant one
    # hour later, which a fixed-offset implementation could never produce.
    first = datetime(2026, 10, 25, 2, 30, tzinfo=PRAGUE, fold=0)
    second = datetime(2026, 10, 25, 2, 30, tzinfo=PRAGUE, fold=1)
    assert first.astimezone(timezone.utc) == datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
    assert second.astimezone(timezone.utc) == datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc)


# --- astronomy.sunrise_sunset -------------------------------------------

def test_prague_offset_is_dst_aware_on_both_sides_of_the_fall_back() -> None:
    """Pins the two offsets the dod calls out by name: Prague is +2 (CEST)
    on 2026-10-24 and +1 (CET) on 2026-10-26, via the same `ZoneInfo`
    construction `sunrise_sunset`'s own `to_local` uses internally."""
    assert datetime(2026, 10, 24, 12, 0, tzinfo=PRAGUE).utcoffset() == _dt.timedelta(hours=2)
    assert datetime(2026, 10, 26, 12, 0, tzinfo=PRAGUE).utcoffset() == _dt.timedelta(hours=1)


def test_sunrise_sunset_tracks_the_fall_back_not_a_fixed_offset() -> None:
    """Unlike the seasonal day-to-day drift on its own (a couple of
    minutes in late October), a fixed-offset bug in `sunrise_sunset`'s
    UTC-to-local conversion would silently carry the wrong side's offset
    into its printed local string. Re-interpreting each day's printed
    local sunrise with that date's own real, unambiguous Prague offset
    should recover nearly the same underlying UTC instant on both sides
    of 2026-10-25 — not the roughly hour-sized jump a fixed offset would
    produce once the wrong offset is applied on top of the right one."""
    before_local, _ = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 10, 24))  # printed in CEST, +2
    after_local, _ = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 10, 26))  # printed in CET, +1

    def as_utc(on: date, hhmm: str) -> datetime:
        h, m = (int(p) for p in hhmm.split(":"))
        return datetime.combine(on, time(h, m), tzinfo=PRAGUE).astimezone(timezone.utc)

    before_utc = as_utc(date(2026, 10, 24), before_local)
    after_utc = as_utc(date(2026, 10, 26), after_local)
    before_minute_of_day = before_utc.hour * 60 + before_utc.minute
    after_minute_of_day = after_utc.hour * 60 + after_utc.minute
    assert abs(after_minute_of_day - before_minute_of_day) < 10


# --- call_sheets.py's "today" cutoff ------------------------------------

def _freeze_now(monkeypatch: pytest.MonkeyPatch, instant_utc: datetime) -> None:
    """Patches `app.routers.call_sheets.datetime.now` so the public "next
    day" endpoint computes its Prague "today" from a fixed UTC instant,
    the same way the real line (`datetime.now(ZoneInfo("Europe/Prague"))`)
    would at that moment in real time."""
    from app.routers import call_sheets as call_sheets_router

    class _Frozen(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return instant_utc.astimezone(tz) if tz is not None else instant_utc

    monkeypatch.setattr(call_sheets_router, "datetime", _Frozen)


def _setup_two_days(client: TestClient, day1: str, day2: str) -> str:
    pid = client.post("/api/v1/productions", json={"name": "Shoot"}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Tomáš Novák"}, headers=AUTH).json()["id"]
    member = client.post(f"/api/v1/productions/{pid}/crew-members",
                          json={"contact_id": cid, "department": "Electric", "position": "Gaffer"}, headers=AUTH).json()
    for i, d in enumerate((day1, day2), start=1):
        r = client.post(f"/api/v1/productions/{pid}/call-sheets",
                         json={"shoot_date": d, "day_number": i, "day_count": 2, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                         headers=AUTH)
        assert r.status_code == 201, r.text
    return member["personal_token"]


def test_today_cutoff_does_not_assume_winter_offset_before_the_fall_back(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """At UTC 2026-10-24 22:30, Prague is still on CEST (+2, the fall-back
    is still hours away) so it is already 2026-10-25 00:30 locally. A
    fixed +1 (CET) assumption would read this as 2026-10-24 23:30 and
    wrongly keep showing the prior day's sheet as "today"."""
    token = _setup_two_days(client, "2026-10-24", "2026-10-25")
    _freeze_now(monkeypatch, datetime(2026, 10, 24, 22, 30, tzinfo=timezone.utc))

    days = client.get(f"/api/v1/public/crew/{token}/next").json()["days"]
    by_date = {d["shoot_date"]: d["call_sheet_id"] for d in days}
    result = client.get(f"/api/v1/public/crew/{token}/next").json()
    assert result["call_sheet_id"] == by_date["2026-10-25"]


def test_today_cutoff_does_not_assume_summer_offset_after_the_fall_back(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """At UTC 2026-10-25 22:30, Prague has already fallen back to CET
    (+1), so it is still 2026-10-25 23:30 locally. A fixed +2 (CEST)
    assumption would read this as 2026-10-26 00:30 and wrongly skip ahead
    to the next day before it has arrived."""
    token = _setup_two_days(client, "2026-10-25", "2026-10-26")
    _freeze_now(monkeypatch, datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc))

    days = client.get(f"/api/v1/public/crew/{token}/next").json()["days"]
    by_date = {d["shoot_date"]: d["call_sheet_id"] for d in days}
    result = client.get(f"/api/v1/public/crew/{token}/next").json()
    assert result["call_sheet_id"] == by_date["2026-10-25"]

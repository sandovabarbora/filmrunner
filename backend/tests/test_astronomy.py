"""Sunrise/sunset formula tests: physical self-consistency plus a pinned
cross-check against sunrise-sunset.org's live answer for Prague (FR-67,
measured 2026-09-22 — see ADR-006). The live comparison itself reruns
daily and on demand in CI (scripts/check_astronomy_accuracy.py), since
this sandbox's own egress proxy still blocks the reference API directly."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services.astronomy import _local_hhmm, _sun_time_utc_hours, sunrise_sunset

PRAGUE_LAT, PRAGUE_LNG = 50.0755, 14.4378


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def test_sunrise_before_sunset_across_the_year():
    d = date(2026, 1, 1)
    while d.year == 2026:
        rise, sset = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, d)
        assert rise is not None and sset is not None
        assert _minutes(rise) < _minutes(sset), f"{d}: sunrise {rise} not before sunset {sset}"
        d += timedelta(days=17)  # sample across the year without a slow per-day loop


def test_day_length_longest_at_summer_solstice_shortest_at_winter():
    def day_length(d: date) -> int:
        rise, sset = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, d)
        return _minutes(sset) - _minutes(rise)

    summer = day_length(date(2026, 6, 21))
    winter = day_length(date(2026, 12, 21))
    spring_eq = day_length(date(2026, 3, 20))
    autumn_eq = day_length(date(2026, 9, 23))

    assert summer > spring_eq > winter
    assert summer > autumn_eq > winter
    # equinoxes should be close to 12h (within the algorithm's known slack)
    assert abs(spring_eq - 12 * 60) < 20
    assert abs(autumn_eq - 12 * 60) < 20


def test_solstices_within_3_minutes_of_a_live_reference():
    """Cross-check against sunrise-sunset.org's actual answer for Prague,
    measured 2026-09-22 by FR-67's CI job (see ADR-006 and
    scripts/check_astronomy_accuracy.py, which reruns this comparison
    live against all four solstices/equinoxes daily and on demand — this
    test pins the two solstice values so a formula regression fails the
    fast local suite too, not only the daily CI job)."""
    summer_rise, summer_set = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 6, 21))
    winter_rise, winter_set = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 12, 21))

    assert abs(_minutes(summer_rise) - _minutes("04:50")) <= 3
    assert abs(_minutes(summer_set) - _minutes("21:17")) <= 3
    assert abs(_minutes(winter_rise) - _minutes("07:56")) <= 3
    assert abs(_minutes(winter_set) - _minutes("16:04")) <= 3


def test_dst_transition_uses_correct_local_offset():
    """Europe/Prague DST starts 2026-03-29; sunrise the week before is CET
    (UTC+1) and the week after is CEST (UTC+2) — a naive fixed-offset
    conversion would be off by an hour on one side."""
    before = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 3, 22))
    after = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 4, 5))
    assert before[0] is not None and after[0] is not None
    # Local sunrise clock time should stay in a similar band across the
    # transition (it does NOT jump forward by an hour) even though the
    # underlying UTC instant does.
    assert abs(_minutes(before[0]) - _minutes(after[0])) < 40


def test_returns_hh_mm_strings():
    rise, sset = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 6, 21))
    assert datetime.strptime(rise, "%H:%M")
    assert datetime.strptime(sset, "%H:%M")


def _exact_local(hours: float, on_date: date) -> datetime:
    midnight = datetime(on_date.year, on_date.month, on_date.day, tzinfo=timezone.utc)
    return (midnight + timedelta(seconds=hours * 3600)).astimezone(ZoneInfo("Europe/Prague"))


def test_the_minute_rounding_up_to_sixty_carries_the_hour():
    """QA's example: 06:59:50 CET was shown as 06:00."""
    assert sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 11, 6))[0] == "07:00"


@pytest.mark.parametrize("lat,lng", [(PRAGUE_LAT, PRAGUE_LNG), (49.1951, 16.6068), (49.8209, 18.2625), (50.77, 15.06)])
def test_every_day_of_two_years_shows_the_exact_time_to_the_nearest_minute(lat: float, lng: float):
    """Every day rather than a sample: the old bug hit about 3% of values, on no particular date."""
    wrong = []
    on_date = date(2026, 1, 1)
    while on_date.year < 2028:
        shown = sunrise_sunset(lat, lng, on_date)
        for is_sunrise, hhmm in ((True, shown[0]), (False, shown[1])):
            exact = _exact_local(_sun_time_utc_hours(is_sunrise, lat, lng, on_date), on_date)
            exact_seconds = exact.hour * 3600 + exact.minute * 60 + exact.second + exact.microsecond / 1e6
            if abs(_minutes(hhmm) * 60 - exact_seconds) > 30.001:
                wrong.append((on_date.isoformat(), is_sunrise, hhmm, exact.time().isoformat()))
        on_date += timedelta(days=1)
    assert not wrong, f"{len(wrong)} wrong, first: {wrong[:3]}"


@pytest.mark.parametrize("hours,on_date,expected", [
    (5.9999, date(2026, 11, 6), "07:00"),  # the minute rolls into the next hour
    (22.9999, date(2026, 11, 6), "00:00"),  # and the hour into the next day
    (23.9999, date(2026, 11, 6), "01:00"),  # the UTC day itself rolls over
    (5.5, date(2026, 6, 21), "07:30"),  # summer offset
    (0.0, date(2026, 11, 6), "01:00"),
])
def test_rounding_boundaries(hours: float, on_date: date, expected: str):
    assert _local_hhmm(hours, on_date, "Europe/Prague") == expected

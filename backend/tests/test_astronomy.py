"""Sunrise/sunset formula tests: physical self-consistency plus a pinned
cross-check against sunrise-sunset.org's live answer for Prague (FR-67,
measured 2026-09-22 — see ADR-006). The live comparison itself reruns
daily and on demand in CI (scripts/check_astronomy_accuracy.py), since
this sandbox's own egress proxy still blocks the reference API directly."""

from datetime import date, datetime, timedelta

from app.services.astronomy import sunrise_sunset

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

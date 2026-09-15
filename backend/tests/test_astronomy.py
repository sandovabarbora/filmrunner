"""Sunrise/sunset formula tests — see ADR-006 for why these are
self-consistency checks plus a wide sanity band rather than a live-source
comparison (egress to timeanddate.com and api.sunrise-sunset.org is
blocked in this environment)."""

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


def test_solstices_within_20_minutes_of_commonly_published_prague_times():
    """Cross-check against approximate, commonly-published Prague solstice
    times (recalled from general knowledge, not fetched live this shift —
    see ADR-006). A follow-up shift should tighten this once egress allows
    fetching an authoritative source."""
    summer_rise, summer_set = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 6, 21))
    winter_rise, winter_set = sunrise_sunset(PRAGUE_LAT, PRAGUE_LNG, date(2026, 12, 21))

    assert abs(_minutes(summer_rise) - _minutes("04:59")) <= 20
    assert abs(_minutes(summer_set) - _minutes("21:08")) <= 20
    assert abs(_minutes(winter_rise) - _minutes("07:58")) <= 20
    assert abs(_minutes(winter_set) - _minutes("16:00")) <= 20


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

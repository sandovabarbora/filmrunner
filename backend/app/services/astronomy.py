"""Sunrise/sunset for a given latitude, longitude and date — no external call.

Implements the standard Sunrise Equation (Astronomical Almanac algorithm),
zenith 90.833 degrees to account for atmospheric refraction and the solar
disk's apparent radius. See ADR-006 for the source references and the
accuracy caveat (not independently verified against a live source this
shift — egress to timeanddate.com and api.sunrise-sunset.org was blocked).

References:
    - https://en.wikipedia.org/wiki/Sunrise_equation
    - https://edwilliams.org/sunrise_sunset_algorithm.htm
"""

import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

_ZENITH = 90.833  # degrees; official sunrise/sunset, includes refraction + solar radius


def _fit_into_range(value: float, lower: float, upper: float) -> float:
    width = upper - lower
    if value < lower:
        return value + width
    if value >= upper:
        return value - width
    return value


def _sun_time_utc_hours(is_sunrise: bool, lat: float, lng: float, on_date: date) -> float | None:
    """Hour of the day (UTC, 0-24) of sunrise or sunset, or None if the sun
    does not rise/set at all on that date at that latitude (polar day/night;
    not reachable for Czech productions, but the formula can return it)."""
    n = on_date.timetuple().tm_yday
    lng_hour = lng / 15
    t = n + ((6 - lng_hour) / 24 if is_sunrise else (18 - lng_hour) / 24)

    m = (0.9856 * t) - 3.289

    l = m + (1.916 * math.sin(math.radians(m))) + (0.020 * math.sin(math.radians(2 * m))) + 282.634
    l = l % 360

    ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l))))
    ra = ra % 360
    l_quadrant = math.floor(l / 90) * 90
    ra_quadrant = math.floor(ra / 90) * 90
    ra = ra + (l_quadrant - ra_quadrant)
    ra_hours = ra / 15

    sin_dec = 0.39782 * math.sin(math.radians(l))
    cos_dec = math.cos(math.asin(sin_dec))

    cos_h = (math.cos(math.radians(_ZENITH)) - (sin_dec * math.sin(math.radians(lat)))) / (
        cos_dec * math.cos(math.radians(lat))
    )
    if cos_h > 1 or cos_h < -1:
        return None  # sun never rises / never sets here on this date

    h = math.degrees(math.acos(cos_h))
    h = (360 - h) if is_sunrise else h
    h_hours = h / 15

    local_mean_time = h_hours + ra_hours - (0.06571 * t) - 6.622
    ut_hours = _fit_into_range(local_mean_time - lng_hour, 0, 24)
    return ut_hours


def sunrise_sunset(lat: float, lng: float, on_date: date, tz_name: str = "Europe/Prague") -> tuple[str, str] | tuple[None, None]:
    """Local "HH:MM" sunrise and sunset for the given coordinates and date,
    or (None, None) if the sun does not rise or set (not expected for
    Czech productions, kept for correctness with any real-world coordinates)."""
    rise_utc = _sun_time_utc_hours(True, lat, lng, on_date)
    set_utc = _sun_time_utc_hours(False, lat, lng, on_date)
    if rise_utc is None or set_utc is None:
        return None, None

    tz = ZoneInfo(tz_name)

    def to_local(hours: float) -> str:
        h = int(hours) % 24
        minute = int(round((hours - int(hours)) * 60)) % 60
        utc_dt = datetime(on_date.year, on_date.month, on_date.day, h, minute, tzinfo=ZoneInfo("UTC"))
        local_dt = utc_dt.astimezone(tz)
        return local_dt.strftime("%H:%M")

    return to_local(rise_utc), to_local(set_utc)

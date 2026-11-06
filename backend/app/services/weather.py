"""Weather suggestion for a shoot date and location, via Open-Meteo — free,
keyless (see ADR-006 for the licence terms: CC-BY 4.0, non-commercial free
tier). A forecast is a suggestion the AD accepts, never an autofill — the
caller is responsible for not overwriting text the AD already typed.

Reference: https://open-meteo.com/en/docs
"""

import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 5.0

# WMO weather interpretation codes (subset used by Open-Meteo), per their docs.
_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def weather_suggestion(lat: float, lng: float, on_date: date) -> str | None:
    """A short text forecast for the date at the coordinates, or None if the
    provider is unreachable, the date is out of its forecast range, or the
    response is not shaped as expected."""
    try:
        response = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "timezone": "Europe/Prague",
                "start_date": on_date.isoformat(),
                "end_date": on_date.isoformat(),
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        daily = data["daily"]
        lo = daily["temperature_2m_min"][0]
        hi = daily["temperature_2m_max"][0]
        code = daily["weather_code"][0]
        if lo is None or hi is None:
            # Open-Meteo still answers 200 for a date past its forecast range,
            # just with null values instead of an error — treat that the same
            # as any other "not shaped as expected" response.
            raise ValueError("no temperature in the forecast for this date")
        description = _WEATHER_CODES.get(code, "forecast unavailable in detail")
        return f"{round(lo)}-{round(hi)}°C, {description}"
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        # Only the class: coordinates show where a shoot is, and httpx puts them in the message through the URL.
        logger.warning("Weather suggestion failed: %s", exc.__class__.__name__)
        return None

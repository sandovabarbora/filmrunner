/**
 * FR-75: the weather suggestion collapses "too far ahead to forecast" and "provider down" into
 * the same generic message (`backend/app/services/weather.py` returns `None` for both by design).
 * Open-Meteo's daily forecast covers roughly this many days ahead (ADR-006's own "~16 days" note,
 * `backend/app/services/weather.py`'s module docstring, and Open-Meteo's own docs). Comparing the
 * shoot date against today plus that window lets the editor tell the two cases apart with no extra
 * network call: a date past the horizon is known in advance to have nothing to fetch.
 */
export const WEATHER_FORECAST_HORIZON_DAYS = 16;

/** Whole days between two ISO dates (UTC midnight to midnight, so a DST switch never shifts it). */
function daysBetween(fromIso: string, toIso: string): number | null {
  const from = new Date(`${fromIso}T00:00:00Z`);
  const to = new Date(`${toIso}T00:00:00Z`);
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return null;
  return Math.round((to.getTime() - from.getTime()) / 86_400_000);
}

/** True when `shootDateIso` is far enough past `todayIso` that Open-Meteo's forecast window
 * cannot possibly cover it. An unparsable date is never treated as beyond the horizon — let the
 * real request answer instead of guessing. */
export function isBeyondWeatherForecastHorizon(shootDateIso: string, todayIso: string): boolean {
  const daysAhead = daysBetween(todayIso, shootDateIso);
  return daysAhead !== null && daysAhead > WEATHER_FORECAST_HORIZON_DAYS;
}

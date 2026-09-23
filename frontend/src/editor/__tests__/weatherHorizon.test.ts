import { describe, expect, it } from "vitest";
import { WEATHER_FORECAST_HORIZON_DAYS, isBeyondWeatherForecastHorizon } from "../weatherHorizon";

describe("isBeyondWeatherForecastHorizon", () => {
  it("is false for a date inside Open-Meteo's forecast window, including the boundary", () => {
    expect(isBeyondWeatherForecastHorizon("2026-09-23", "2026-09-23")).toBe(false); // today
    expect(isBeyondWeatherForecastHorizon("2026-10-01", "2026-09-23")).toBe(false); // 8 days out
    expect(isBeyondWeatherForecastHorizon("2026-10-08", "2026-09-23")).toBe(false); // 15 days out
    const boundary = new Date("2026-09-23T00:00:00Z");
    boundary.setUTCDate(boundary.getUTCDate() + WEATHER_FORECAST_HORIZON_DAYS);
    expect(isBeyondWeatherForecastHorizon(boundary.toISOString().slice(0, 10), "2026-09-23")).toBe(false); // exactly on the horizon
  });

  it("is true once the shoot date is past the horizon", () => {
    const beyond = new Date("2026-09-23T00:00:00Z");
    beyond.setUTCDate(beyond.getUTCDate() + WEATHER_FORECAST_HORIZON_DAYS + 1);
    expect(isBeyondWeatherForecastHorizon(beyond.toISOString().slice(0, 10), "2026-09-23")).toBe(true);
    expect(isBeyondWeatherForecastHorizon("2027-01-01", "2026-09-23")).toBe(true); // months out
  });

  it("is false for a date in the past (the provider, not the horizon check, should answer)", () => {
    expect(isBeyondWeatherForecastHorizon("2026-01-01", "2026-09-23")).toBe(false);
  });

  it("never treats an unparsable date as beyond the horizon", () => {
    expect(isBeyondWeatherForecastHorizon("not-a-date", "2026-09-23")).toBe(false);
    expect(isBeyondWeatherForecastHorizon("2026-09-23", "not-a-date")).toBe(false);
  });
});

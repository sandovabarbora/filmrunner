"""Geocoding, weather, and nearest-hospital services: every external call
is mocked (see ADR-006 — this environment's egress is blocked for these
providers too, same as FR-18's monkeypatched storage calls). What's under
test is our own handling: request shape, response parsing, and that every
failure mode falls back to None instead of raising."""

from datetime import date

import httpx
import pytest

from app.services import geocoding, hospitals, weather


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


# --- geocoding -----------------------------------------------------------


def test_geocode_success(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert "User-Agent" in headers
        assert params["q"] == "Staroměstské náměstí, Praha"
        return _FakeResponse([{"lat": "50.0870", "lon": "14.4208", "display_name": "Staroměstské náměstí, Praha 1"}])

    monkeypatch.setattr(geocoding.httpx, "get", fake_get)
    result = geocoding.geocode("Staroměstské náměstí, Praha")
    assert result is not None
    assert result.lat == pytest.approx(50.0870)
    assert result.lng == pytest.approx(14.4208)
    assert result.display_name == "Staroměstské náměstí, Praha 1"


def test_geocode_no_match_returns_none(monkeypatch):
    monkeypatch.setattr(geocoding.httpx, "get", lambda *a, **k: _FakeResponse([]))
    assert geocoding.geocode("somewhere that does not exist xyzzy") is None


def test_geocode_timeout_returns_none_not_raise(monkeypatch):
    def fake_get(*a, **k):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(geocoding.httpx, "get", fake_get)
    assert geocoding.geocode("Praha") is None


def test_geocode_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(geocoding.httpx, "get", lambda *a, **k: _FakeResponse([{"unexpected": "shape"}]))
    assert geocoding.geocode("Praha") is None


def test_geocode_blank_address_returns_none_without_calling_out(monkeypatch):
    def fake_get(*a, **k):
        raise AssertionError("should not call the geocoder for a blank address")

    monkeypatch.setattr(geocoding.httpx, "get", fake_get)
    assert geocoding.geocode("   ") is None


# --- weather ---------------------------------------------------------------


def test_weather_suggestion_success(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        assert params["latitude"] == 50.0755
        return _FakeResponse({"daily": {"temperature_2m_max": [18.4], "temperature_2m_min": [9.1], "weather_code": [61]}})

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    result = weather.weather_suggestion(50.0755, 14.4378, date(2026, 6, 21))
    assert result == "9-18°C, slight rain"


def test_weather_suggestion_unreachable_returns_none(monkeypatch):
    monkeypatch.setattr(weather.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert weather.weather_suggestion(50.0755, 14.4378, date(2026, 6, 21)) is None


def test_weather_suggestion_unknown_code_still_returns_temperatures(monkeypatch):
    monkeypatch.setattr(
        weather.httpx,
        "get",
        lambda *a, **k: _FakeResponse({"daily": {"temperature_2m_max": [5.0], "temperature_2m_min": [1.0], "weather_code": [9999]}}),
    )
    result = weather.weather_suggestion(50.0755, 14.4378, date(2026, 1, 5))
    assert result == "1-5°C, forecast unavailable in detail"


def test_weather_suggestion_malformed_response_returns_none(monkeypatch):
    monkeypatch.setattr(weather.httpx, "get", lambda *a, **k: _FakeResponse({"unexpected": "shape"}))
    assert weather.weather_suggestion(50.0755, 14.4378, date(2026, 6, 21)) is None


# --- nearest hospital --------------------------------------------------------


def test_nearest_hospital_picks_the_closest(monkeypatch):
    elements = [
        {"lat": 50.10, "lon": 14.50, "tags": {"name": "Far Hospital"}},
        {"lat": 50.076, "lon": 14.44, "tags": {"name": "Nemocnice Na Bulovce", "addr:street": "Budínova", "addr:housenumber": "2", "addr:city": "Praha 8"}},
    ]
    monkeypatch.setattr(hospitals.httpx, "post", lambda *a, **k: _FakeResponse({"elements": elements}))
    result = hospitals.nearest_hospital_suggestion(50.0755, 14.4378)
    assert result == "Nemocnice Na Bulovce, Budínova 2 Praha 8"


def test_nearest_hospital_no_results_returns_none(monkeypatch):
    monkeypatch.setattr(hospitals.httpx, "post", lambda *a, **k: _FakeResponse({"elements": []}))
    assert hospitals.nearest_hospital_suggestion(50.0755, 14.4378) is None


def test_nearest_hospital_unreachable_returns_none(monkeypatch):
    monkeypatch.setattr(hospitals.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert hospitals.nearest_hospital_suggestion(50.0755, 14.4378) is None


def test_nearest_hospital_skips_unnamed_nodes(monkeypatch):
    elements = [{"lat": 50.076, "lon": 14.44, "tags": {}}]
    monkeypatch.setattr(hospitals.httpx, "post", lambda *a, **k: _FakeResponse({"elements": elements}))
    assert hospitals.nearest_hospital_suggestion(50.0755, 14.4378) is None

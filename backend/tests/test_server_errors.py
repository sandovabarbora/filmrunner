"""FR-222: a 500 must reach the browser as a 500. Without CORS headers the browser hides the response from
the page, the editor reads it as no connection, and the AD keeps retrying something that will never work."""

import logging

import pytest
from fastapi.testclient import TestClient

from app import errors
from app.config import get_settings
from app.routers import call_sheets as call_sheets_router
from app.routers import dashboard as dashboard_router

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
ORIGIN = {"Origin": "https://sandovabarbora.github.io"}


@pytest.fixture(autouse=True)
def _logger_enabled(monkeypatch) -> None:
    # A migration test running Alembic earlier in the session applies fileConfig, which disables existing loggers.
    monkeypatch.setattr(errors.logger, "disabled", False)


def _boom(*_args, **_kwargs):
    raise RuntimeError("leaky internals: table call_sheets, host db.internal")


def test_an_unhandled_error_is_a_500_the_browser_can_read(client: TestClient, monkeypatch, caplog) -> None:
    monkeypatch.setattr(dashboard_router, "build_dashboard", _boom)
    with caplog.at_level(logging.ERROR):
        r = client.get("/api/v1/me/dashboard", headers={**AUTH, **ORIGIN})
    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] in ("*", ORIGIN["Origin"])
    assert r.json() == {"detail": "Internal server error"}
    assert "leaky" not in r.text and "Traceback" not in r.text
    assert "RuntimeError: leaky internals" in caplog.text and "Traceback" in caplog.text


def test_the_log_does_not_carry_a_personal_link(client: TestClient, monkeypatch, caplog) -> None:
    monkeypatch.setattr(call_sheets_router, "next_day_for_token", _boom)
    with caplog.at_level(logging.ERROR, logger="app"):
        r = client.get("/api/v1/public/crew/the-persons-secret-token/next", headers=ORIGIN)
    assert r.status_code == 500 and r.headers["access-control-allow-origin"]
    errors = "\n".join(record.getMessage() for record in caplog.records if record.name.startswith("app"))
    assert "/public/crew/{token}/next" in errors
    assert "the-persons-secret-token" not in errors


def test_handled_errors_keep_their_own_status_and_detail(client: TestClient) -> None:
    r = client.get("/api/v1/call-sheets/00000000-0000-0000-0000-000000000000", headers={**AUTH, **ORIGIN})
    assert r.status_code == 404 and r.json()["detail"] == "Call sheet not found"


def test_preflight_still_answers(client: TestClient) -> None:
    r = client.options("/api/v1/me/dashboard", headers={**ORIGIN, "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200

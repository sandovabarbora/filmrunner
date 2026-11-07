"""FR-222: a 500 must reach the browser as a 500. Without CORS headers the browser hides the response from
the page, the editor reads it as no connection, and the AD keeps retrying something that will never work."""

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import errors
from app.config import get_settings
from app.database import engine
from app.routers import call_sheets as call_sheets_router
from app.routers import dashboard as dashboard_router

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
ORIGIN = {"Origin": "https://sandovabarbora.github.io"}


@pytest.fixture(autouse=True)
def _logger_enabled(monkeypatch) -> None:
    # A migration test running Alembic earlier in the session applies fileConfig, which disables existing loggers.
    monkeypatch.setattr(errors.logger, "disabled", False)


# Module constants: the logged frames show source lines, which are not what these tests are looking for.
LEAK = "leaky internals: table call_sheets, host db.internal"
CAUSE = "cause with a phone number 777000111"


def _boom(*_args, **_kwargs):
    raise RuntimeError(LEAK)


def test_an_unhandled_error_is_a_500_the_browser_can_read(client: TestClient, monkeypatch, caplog) -> None:
    monkeypatch.setattr(dashboard_router, "build_dashboard", _boom)
    with caplog.at_level(logging.ERROR):
        r = client.get("/api/v1/me/dashboard", headers={**AUTH, **ORIGIN})
    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] in ("*", ORIGIN["Origin"])
    assert r.json() == {"detail": "Internal server error"}
    assert "leaky" not in r.text and "Traceback" not in r.text
    assert "RuntimeError" in caplog.text and "test_server_errors.py" in caplog.text
    assert "leaky" not in caplog.text


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


def test_postgres_detail_text_stays_out_of_the_log(client: TestClient, monkeypatch, caplog) -> None:
    """hide_parameters covers bound values, not the server's own DETAIL line, which quotes the conflicting value."""
    row_value = "value-from-the-conflicting-row"

    def violate_a_unique_constraint(*_args, **_kwargs):
        with engine.connect() as connection:
            connection.execute(text("CREATE TEMP TABLE probe (token text UNIQUE)"))
            connection.execute(text(f"INSERT INTO probe VALUES ('{row_value}')"))
            connection.execute(text(f"INSERT INTO probe VALUES ('{row_value}')"))

    monkeypatch.setattr(dashboard_router, "build_dashboard", violate_a_unique_constraint)
    with caplog.at_level(logging.ERROR, logger="app"):
        r = client.get("/api/v1/me/dashboard", headers={**AUTH, **ORIGIN})
    assert r.status_code == 500
    assert "IntegrityError" in caplog.text
    assert row_value not in caplog.text
    assert "already exists" not in caplog.text


def test_the_log_keeps_where_it_failed_and_what_caused_it_but_not_the_messages(client: TestClient, monkeypatch, caplog) -> None:
    def chained(*_args, **_kwargs):
        try:
            raise ValueError(CAUSE)
        except ValueError as exc:
            raise RuntimeError(LEAK) from exc

    monkeypatch.setattr(dashboard_router, "build_dashboard", chained)
    with caplog.at_level(logging.ERROR, logger="app"):
        assert client.get("/api/v1/me/dashboard", headers={**AUTH, **ORIGIN}).status_code == 500
    assert "RuntimeError" in caplog.text and "ValueError" in caplog.text and "test_server_errors.py" in caplog.text
    assert "leaky internals" not in caplog.text and "777000111" not in caplog.text


ROW_DETAIL = "DETAIL:  Key (personal_token)=(value-from-the-row) already exists."


def test_a_failed_test_world_purge_logs_no_message(client: TestClient, monkeypatch, caplog) -> None:
    """FR-222 review: this was logger.exception, so Postgres's DETAIL line reached the log."""
    from sqlalchemy.exc import IntegrityError

    from app.config import get_settings
    from app.routers import sandbox as sandbox_router

    def failing_purge(_db):
        raise IntegrityError("DELETE FROM contacts", {}, Exception(ROW_DETAIL))

    monkeypatch.setattr(get_settings(), "sandbox_enabled", True)
    monkeypatch.setattr(sandbox_router, "purge_expired", failing_purge)
    monkeypatch.setattr(sandbox_router.logger, "disabled", False)
    sandbox_router._per_ip.reset()
    with caplog.at_level(logging.ERROR, logger="app"):
        r = client.post("/api/v1/public/sandbox/sessions", headers=ORIGIN)
    assert r.status_code < 300, r.text
    assert "Could not purge expired test worlds" in caplog.text and "IntegrityError" in caplog.text
    assert "value-from-the-row" not in caplog.text and "already exists" not in caplog.text


def test_a_client_that_hangs_up_mid_body_is_not_logged_as_an_unhandled_error(caplog) -> None:
    """FastAPI turns ClientDisconnect while reading a body into a 400 before the route runs, so it never reaches
    UnhandledErrorMiddleware. Checked on the real stack, so a FastAPI upgrade that changes this fails here."""
    import asyncio

    from app.main import app

    async def run(path: str, content_type: bytes) -> list[dict]:
        sent: list[dict] = []
        parts = iter([{"type": "http.request", "body": b'{"name"', "more_body": True}])

        async def receive():
            return next(parts, {"type": "http.disconnect"})

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http", "path": path,
                 "raw_path": path.encode(), "query_string": b"", "root_path": "", "client": ("192.0.2.1", 1), "server": ("testserver", 80),
                 "headers": [(b"content-type", content_type), (b"authorization", AUTH["Authorization"].encode())]}
        await app(scope, receive, send)
        return sent

    with caplog.at_level(logging.WARNING):
        json_post = asyncio.run(run("/api/v1/productions", b"application/json"))
        upload = asyncio.run(run(f"/api/v1/contacts/{uuid.uuid4()}/photo", b"multipart/form-data; boundary=x"))
    statuses = [m["status"] for m in json_post + upload if m["type"] == "http.response.start"]
    assert all(s < 500 for s in statuses), statuses
    assert not [r for r in caplog.records if r.name == "app.errors"]

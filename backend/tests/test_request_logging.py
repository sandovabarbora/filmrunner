"""FR-223: personal tokens are credentials and live in URL paths, so no log line may carry a path."""

import asyncio
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.request_log import RequestLogMiddleware
from app.auth import Principal, require_principal
from app.main import app
from app.services import geocoding, hospitals, push, weather

CREW_LINK = "crew-link-value-do-not-log-4f1c"
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _loggers_enabled():
    # test_migration_enum_casing.py runs Alembic in this process, and its fileConfig disables every existing logger.
    for name in ("filmrunner.request", geocoding.logger.name, push.logger.name, weather.logger.name, hospitals.logger.name,
                 "app.routers.call_sheets", "app.routers.productions"):
        logging.getLogger(name).disabled = False


def _everything(caplog) -> str:
    return "\n".join(f"{r.name} {r.getMessage()} {r.exc_text or ''}" for r in caplog.records)


@pytest.mark.parametrize("path", [
    f"/api/v1/public/crew/{CREW_LINK}/next",
    f"/api/v1/public/call-sheets/00000000-0000-0000-0000-000000000000/me/{CREW_LINK}",
    f"/api/v1/public/call-sheets/00000000-0000-0000-0000-000000000000/seen/{CREW_LINK}",
    f"/definitely/not/a/route/{CREW_LINK}",
])
def test_a_personal_token_never_reaches_the_logs(client, caplog, path):
    with caplog.at_level(logging.DEBUG):
        client.get(path)
        client.post(path)
    assert CREW_LINK not in _everything(caplog)
    assert any(r.name == "filmrunner.request" for r in caplog.records)


def test_the_line_has_method_route_template_status_duration_and_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="filmrunner.request"):
        client.get(f"/api/v1/public/crew/{CREW_LINK}/next", headers={"fly-request-id": "01ABC-def_9"})
    line = next(r.getMessage() for r in caplog.records if r.name == "filmrunner.request")
    assert line.startswith("GET /public/crew/{token}/next 404 ")
    assert "ms" in line
    assert "request_id=01ABC-def_9" in line


def test_a_forged_request_id_cannot_inject_a_log_line(client, caplog):
    with caplog.at_level(logging.INFO, logger="filmrunner.request"):
        client.get("/healthz", headers={"fly-request-id": "x GET /fake 200 link=" + CREW_LINK})
    line = next(r.getMessage() for r in caplog.records if r.name == "filmrunner.request")
    assert line.endswith("request_id=-")


def _run(asgi_app) -> None:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    asyncio.run(RequestLogMiddleware(asgi_app)({"type": "http", "method": "GET", "headers": []}, receive, send))


def test_a_crash_is_logged_as_500_and_still_raises(caplog):
    async def crashes(scope, receive, send):
        raise RuntimeError("boom")

    with caplog.at_level(logging.INFO, logger="filmrunner.request"), pytest.raises(RuntimeError):
        _run(crashes)
    assert " 500 " in caplog.records[-1].getMessage()


def test_background_work_after_the_response_is_not_counted_as_request_time(caplog):
    logged_before_background = []

    async def responds_then_works(scope, receive, send):
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        logged_before_background.append(len(caplog.records))

    with caplog.at_level(logging.INFO, logger="filmrunner.request"):
        _run(responds_then_works)
    assert logged_before_background == [1]
    assert len(caplog.records) == 1


def test_the_container_runs_without_uvicorn_access_logs():
    cmd = next(line for line in (BACKEND / "Dockerfile").read_text().splitlines() if line.startswith("CMD"))
    assert '"--no-access-log"' in cmd


def test_a_failed_geocode_does_not_log_the_address(monkeypatch, caplog):
    address = "Tajna ulice 7, Praha"
    request = httpx.Request("GET", "https://nominatim.example/search", params={"q": address})

    def fails(*args, **kwargs):
        raise httpx.HTTPStatusError(f"503 for url {request.url}", request=request, response=httpx.Response(503, request=request))

    monkeypatch.setattr(geocoding.httpx, "get", fails)
    with caplog.at_level(logging.DEBUG):
        assert geocoding.geocode(address) is None
    logged = _everything(caplog)
    assert "Tajna" not in logged and "Geocoding failed" in logged


def test_an_unexpected_geocoder_shape_does_not_log_the_address(monkeypatch, caplog):
    request = httpx.Request("GET", "https://nominatim.example/search")
    monkeypatch.setattr(geocoding.httpx, "get", lambda *a, **k: httpx.Response(200, json=[{"nope": 1}], request=request))
    with caplog.at_level(logging.DEBUG):
        assert geocoding.geocode("Tajna ulice 7, Praha") is None
    assert "Tajna" not in _everything(caplog)


def test_http_client_libraries_cannot_log_urls_even_at_debug():
    for name in ("httpx", "httpcore", "urllib3"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING


def test_a_failed_push_logs_neither_the_endpoint_nor_a_reason_carrying_it(monkeypatch, caplog):
    settings = push.get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "public")
    monkeypatch.setattr(settings, "vapid_private_key", "private")

    def fails(**kwargs):
        raise ConnectionError("Max retries exceeded with url: /wpush/private-endpoint-path")

    monkeypatch.setattr(push, "webpush", fails)
    with caplog.at_level(logging.DEBUG), pytest.raises(push.PushDeliveryError) as caught:
        push.send(endpoint="https://fcm.googleapis.com/wpush/private-endpoint-path", p256dh="x", auth="y", payload={})
    assert "private-endpoint-path" not in _everything(caplog)
    assert "private-endpoint-path" not in caught.value.reason
    assert "fcm.googleapis.com" in _everything(caplog)


def test_the_geocoder_user_agent_has_a_project_url_and_no_address():
    assert "github.com/sandovabarbora/filmrunner" in geocoding._USER_AGENT
    assert "@" not in geocoding._USER_AGENT


def _http_failure_quoting_the_url(*args, **kwargs):
    request = httpx.Request("GET", "https://provider.example/?latitude=50.0755&longitude=14.4378")
    raise httpx.HTTPStatusError(f"503 for url {request.url}", request=request, response=httpx.Response(503, request=request))


def test_a_failed_weather_call_logs_only_the_exception_class(monkeypatch, caplog):
    monkeypatch.setattr(weather.httpx, "get", _http_failure_quoting_the_url)
    with caplog.at_level(logging.DEBUG):
        assert weather.weather_suggestion(50.0755, 14.4378, date(2026, 6, 21)) is None
    logged = _everything(caplog)
    assert "HTTPStatusError" in logged and "50.0755" not in logged and "provider.example" not in logged


def test_a_failed_hospital_lookup_logs_only_the_exception_class(monkeypatch, caplog):
    monkeypatch.setattr(hospitals.httpx, "post", _http_failure_quoting_the_url)
    with caplog.at_level(logging.DEBUG):
        assert hospitals.nearest_hospital_suggestion(50.0755, 14.4378) is None
    logged = _everything(caplog)
    assert "HTTPStatusError" in logged and "50.0755" not in logged and "provider.example" not in logged


def test_no_audit_log_line_carries_the_users_email(client, caplog):
    email = "person.name@example.com"
    app.dependency_overrides[require_principal] = lambda: Principal(kind="user", subject="user-1", email=email)
    with caplog.at_level(logging.INFO):
        production = client.post("/api/v1/productions", json={"name": "Logging test"})
        assert production.status_code == 201, production.text
        sheet = client.post(f"/api/v1/productions/{production.json()['id']}/call-sheets", json={
            "shoot_date": "2030-01-01", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "05:00"},
        })
        assert sheet.status_code == 201, sheet.text
        sheet_url = f"/api/v1/call-sheets/{sheet.json()['id']}"
        assert client.post(f"{sheet_url}/cancel").status_code == 200
        assert client.post(f"{sheet_url}/restore").status_code == 200
    logged = _everything(caplog)
    assert email not in logged
    assert "cancelled by user" in logged and "restored by user" in logged and "by user" in logged.split("Created production")[1]


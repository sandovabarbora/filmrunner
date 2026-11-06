"""FR-223: personal tokens are credentials and live in URL paths, so no log line may carry a path."""

import asyncio
import logging
from pathlib import Path

import httpx
import pytest

from app.request_log import RequestLogMiddleware
from app.services import geocoding, push

CREW_LINK = "crew-link-value-do-not-log-4f1c"
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _loggers_enabled():
    # test_migration_enum_casing.py runs Alembic in this process, and its fileConfig disables every existing logger.
    for name in ("filmrunner.request", geocoding.logger.name, push.logger.name):
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

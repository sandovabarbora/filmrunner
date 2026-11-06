"""FR-223: /readyz says whether the database answers; /healthz stays a pure process check."""

import time
import tomllib
from pathlib import Path

from sqlalchemy import create_engine

import app.main as main_module

BACKEND = Path(__file__).resolve().parents[1]


def _dead_engine():
    return create_engine("postgresql+psycopg://leak_me_user@127.0.0.1:1/leak_me_db", connect_args={"connect_timeout": 1})


def test_readyz_is_ok_when_the_database_answers(client, monkeypatch):
    monkeypatch.setattr(main_module.settings, "git_sha", "abc123")
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["git_sha"] == "abc123"


def test_readyz_is_503_without_details_when_the_database_is_unreachable(client, monkeypatch):
    monkeypatch.setattr(main_module, "engine", _dead_engine())
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "leak_me" not in response.text


def test_readyz_answers_quickly_when_the_database_hangs(client, monkeypatch):
    monkeypatch.setattr(main_module, "_select_one", lambda: time.sleep(main_module.READY_TIMEOUT_SECONDS + 1))
    started = time.monotonic()
    response = client.get("/readyz")
    assert response.status_code == 503
    assert time.monotonic() - started < main_module.READY_TIMEOUT_SECONDS + 0.5


def test_healthz_stays_up_when_the_database_is_unreachable(client, monkeypatch):
    monkeypatch.setattr(main_module, "engine", _dead_engine())
    assert client.get("/healthz").status_code == 200


def test_fly_keeps_a_machine_running_and_checks_liveness_not_the_database():
    service = tomllib.loads((BACKEND / "fly.toml").read_text())["http_service"]
    assert service["min_machines_running"] == 1
    assert [check["path"] for check in service["checks"]] == ["/healthz"]

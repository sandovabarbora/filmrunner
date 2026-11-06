"""FR-12: Supabase JWT (ES256 via JWKS) or the service token; identity drives created_by.

The JWKS client is replaced with a local ES256 key pair so the test needs
no network and no Supabase project.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.config import get_settings

SERVICE = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


@pytest.fixture()
def keys(monkeypatch: pytest.MonkeyPatch):
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()

    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token: str):
            class Key:
                key = public
            return Key()

    monkeypatch.setattr(auth, "_jwk_client", lambda: FakeJwkClient())
    return private


def _token(private, **claims) -> str:
    now = int(time.time())
    payload = {"sub": "user-1", "email": "eva@example.com", "aud": "authenticated", "role": "authenticated",
               "iat": now, "exp": now + 600, **claims}
    return jwt.encode(payload, private, algorithm="ES256", headers={"kid": "test"})


def test_supabase_jwt_is_accepted_and_sets_created_by(client: TestClient, keys) -> None:
    headers = {"Authorization": f"Bearer {_token(keys)}"}
    pid = client.post("/api/v1/productions", json={"name": "Auth test"}, headers=headers).json()["id"]
    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1,
              "initial_revision": {"general_crew_call": "06:30", "created_by": "spoofed", "schedule_items": []}},
        headers=headers,
    )
    assert sheet.status_code == 201, sheet.text
    assert sheet.json()["current_revision"]["created_by"] == "eva@example.com"  # identity wins over the body


def test_expired_jwt_is_rejected(client: TestClient, keys) -> None:
    token = _token(keys, exp=int(time.time()) - 10)
    resp = client.get("/api/v1/productions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_wrong_audience_is_rejected(client: TestClient, keys) -> None:
    token = _token(keys, aud="anon")
    resp = client.get("/api/v1/productions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_garbage_bearer_is_rejected(client: TestClient, keys) -> None:
    resp = client.get("/api/v1/productions", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_service_token_still_works_and_is_labelled(client: TestClient, keys) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Service"}, headers=SERVICE).json()["id"]
    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1,
              "initial_revision": {"general_crew_call": "06:30", "created_by": "seed_demo.py", "schedule_items": []}},
        headers=SERVICE,
    ).json()
    assert sheet["current_revision"]["created_by"] == "service:seed_demo.py"


def test_the_service_token_is_compared_in_constant_time(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[bytes, bytes]] = []
    real = auth.hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(auth.hmac, "compare_digest", spy)
    assert client.get("/api/v1/productions", headers=SERVICE).status_code == 200
    assert calls


def test_a_non_ascii_bearer_token_is_a_401_not_a_crash(client: TestClient) -> None:
    """Failure case: compare_digest raises TypeError on a non-ASCII str, so both sides go in as bytes."""
    resp = client.get("/api/v1/productions", headers={"Authorization": "Bearer žluťoučký".encode()})
    assert resp.status_code == 401

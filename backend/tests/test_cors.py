"""FR-129: CORS and auth-header regression after this month's fastapi/
starlette/pyjwt bumps (FR-100/FR-110/FR-117).

Builds a fresh app per test using the exact `CORSMiddleware` call `app/main.py`
wires (`allow_origins=..., allow_methods=["*"], allow_headers=["*"]`, no
`allow_credentials`), against a restricted origin list — the live app's own
CORS middleware is already constructed at import time from this sandbox's
wildcard dev config (`FILMRUNNER_CORS_ORIGINS` unset), so it can't be
re-exercised with a different origin list without re-importing the module.
This still catches a version bump that changes `CORSMiddleware`'s own
defaults (e.g. a looser default `allow_credentials`), because it is the same
class, same arguments, same starlette/fastapi version as production.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.auth import require_principal
from app.config import get_settings
from app.main import app as production_app

ALLOWED_ORIGIN = "https://sandovabarbora.github.io"
DISALLOWED_ORIGIN = "https://evil.example"


def _build_app(allow_origins: list[str]) -> FastAPI:
    """Mirror app/main.py's own CORSMiddleware wiring, with one protected route."""
    test_app = FastAPI()
    test_app.add_middleware(CORSMiddleware, allow_origins=allow_origins, allow_methods=["*"], allow_headers=["*"])

    @test_app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    @test_app.get("/whoami")
    def whoami(principal=Depends(require_principal)) -> dict[str, str]:
        return {"kind": principal.kind}

    return test_app


def test_production_cors_never_pairs_wildcard_origin_with_credentials() -> None:
    """Reads the live app's own middleware stack, not a copy of it: if
    `allow_credentials=True` is ever added to app/main.py's CORSMiddleware
    call without also narrowing allow_origins away from "*", this fails —
    that combination is the one real browsers refuse to honour anyway, but
    better to catch it here than find out from a bug report."""
    cors = next(m for m in production_app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    allow_origins = cors.kwargs.get("allow_origins", ())
    allow_credentials = cors.kwargs.get("allow_credentials", False)
    if "*" in allow_origins:
        assert allow_credentials is False


def test_disallowed_origin_gets_no_cors_headers() -> None:
    test_app = _build_app([ALLOWED_ORIGIN])
    with TestClient(test_app) as client:
        resp = client.get("/ping", headers={"Origin": DISALLOWED_ORIGIN})
        assert resp.status_code == 200  # the server still answers; the browser is what refuses
        assert "access-control-allow-origin" not in resp.headers


def test_preflight_for_disallowed_origin_is_not_authorized() -> None:
    test_app = _build_app([ALLOWED_ORIGIN])
    with TestClient(test_app) as client:
        resp = client.options(
            "/ping",
            headers={
                "Origin": DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert "access-control-allow-origin" not in resp.headers


def test_allowed_origin_is_reflected_back() -> None:
    test_app = _build_app([ALLOWED_ORIGIN])
    with TestClient(test_app) as client:
        resp = client.get("/ping", headers={"Origin": ALLOWED_ORIGIN})
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_preflight_allows_the_authorization_header_for_an_allowed_origin() -> None:
    """The personal-link/service-token auth this app uses travels as an
    Authorization header, never a cookie — allow_headers=["*"] must keep
    covering it after the bump, or every real client request would fail its
    own browser-side preflight before the server ever saw it."""
    test_app = _build_app([ALLOWED_ORIGIN])
    with TestClient(test_app) as client:
        resp = client.options(
            "/ping",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_valid_bearer_auth_still_works_through_a_restricted_cors_origin() -> None:
    """Combines both bumps in one request: a restricted CORS origin plus the
    real auth dependency, using the service token exactly as test_auth.py
    does, so a regression in either the CORS or the auth-header plumbing
    shows up as one failing request rather than two separately-green ones."""
    test_app = _build_app([ALLOWED_ORIGIN])
    with TestClient(test_app) as client:
        resp = client.get(
            "/whoami",
            headers={"Origin": ALLOWED_ORIGIN, "Authorization": f"Bearer {get_settings().api_bearer_token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"kind": "service"}
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

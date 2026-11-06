"""Who is calling: a Supabase user (JWT) or a service script (shared token).

Supabase Auth signs access tokens with asymmetric keys (ES256 for this
project); the public keys are served at
`<supabase_url>/auth/v1/.well-known/jwks.json` and may be cached for at
most 10 minutes. The service token stays for seeding and tests only.

References:
    - https://supabase.com/docs/guides/auth/jwts
    - https://pyjwt.readthedocs.io/en/stable/usage.html#retrieve-rsa-signing-keys-from-a-jwks-endpoint
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app import sandbox_tokens
from app.config import get_settings
from app.ratelimit import SlidingWindow

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)
_sandbox_requests = SlidingWindow(300)  # per persona, per minute: generous for a person, a brake on a script
_JWT_ALGORITHMS = ["ES256", "RS256"]
_JWKS_LIFESPAN_SECONDS = 600  # Supabase: do not cache the JWKS longer than 10 minutes


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, as recorded in audit fields."""

    kind: str  # "user" or "service"
    subject: str  # user id, or "service"
    email: str | None

    @property
    def label(self) -> str:
        """Value stored in created_by: the user's email, or a service marker."""
        return self.email or self.subject


@lru_cache
def _jwk_client() -> PyJWKClient:
    settings = get_settings()
    if not settings.supabase_url:
        raise RuntimeError("FILMRUNNER_SUPABASE_URL is not set; user sign-in is disabled")
    return PyJWKClient(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        lifespan=_JWKS_LIFESPAN_SECONDS,
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def _principal_from_jwt(token: str) -> Principal:
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=_JWT_ALGORITHMS, audience="authenticated")
    except RuntimeError as exc:
        logger.warning("JWT presented but sign-in is not configured: %s", exc)
        raise _unauthorized("Sign-in is not configured on this server") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired sign-in token") from exc
    return Principal(kind="user", subject=str(claims.get("sub", "")), email=claims.get("email"))


def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Principal:
    """Resolve the caller or raise 401.

    The service token is compared first because it is cheap and needs no
    network; everything else must be a valid Supabase JWT.
    """
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    token = credentials.credentials
    if token == get_settings().api_bearer_token:
        return Principal(kind="service", subject="service", email=None)
    # A test persona is an ordinary signed-in user who is a member of test productions only, so every access rule applies unchanged.
    sandbox = sandbox_tokens.read_token(token) if get_settings().sandbox_enabled else None
    if sandbox is not None:
        allowed, retry_after = _sandbox_requests.hit(str(sandbox["sub"]))
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests", headers={"Retry-After": str(retry_after)})
        return Principal(kind="user", subject=str(sandbox["sub"]), email=sandbox["email"])
    return _principal_from_jwt(token)


def require_api_token(principal: Principal = Depends(require_principal)) -> None:
    """Kept for routers that only need "someone is signed in"."""
    return None

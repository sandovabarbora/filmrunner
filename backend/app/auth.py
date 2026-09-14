"""Stub bearer-token auth.

NOT a real auth system — the full FilmRunner spec calls for SSO/SAML, which
is explicitly out of scope for this skeleton (see DESIGN.md). This exists
only so every endpoint is behind *something* rather than wide open, and so
swapping in real auth later means replacing one dependency, not touching
every router.

Reference: https://fastapi.tiangolo.com/tutorial/security/first-steps/
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    settings = get_settings()
    if credentials is None or credentials.credentials != settings.api_bearer_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

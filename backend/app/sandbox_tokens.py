import hashlib
import hmac
import time
from datetime import datetime

import jwt

from app.config import get_settings

SANDBOX_EMAIL_DOMAIN = "sandbox.invalid"
_ISSUER = "filmrunner-sandbox"


def _signing_key() -> bytes:
    # Derived, so a sandbox token can never double as the service token or reveal it.
    return hmac.new(get_settings().api_bearer_token.encode(), b"filmrunner-sandbox", hashlib.sha256).digest()


def sandbox_email(session: str, persona: str) -> str:
    return f"{persona}.{session}@{SANDBOX_EMAIL_DOMAIN}"


def session_of_email(email: str | None) -> str | None:
    """The sandbox session a persona belongs to; None for every real person."""
    if not email or not email.endswith(f"@{SANDBOX_EMAIL_DOMAIN}"):
        return None
    return email.split("@")[0].rsplit(".", 1)[-1]


def issue_token(session: str, persona: str, expires_at: datetime) -> str:
    claims = {"iss": _ISSUER, "sub": f"sandbox-{session}-{persona}", "email": sandbox_email(session, persona),
              "iat": int(time.time()), "exp": int(expires_at.timestamp())}
    return jwt.encode(claims, _signing_key(), algorithm="HS256")


def read_token(token: str) -> dict | None:
    """The claims of a valid sandbox token; None for any other token, which then takes the normal sign-in path."""
    try:
        if jwt.get_unverified_header(token).get("alg") != "HS256":
            return None
        return jwt.decode(token, _signing_key(), algorithms=["HS256"], issuer=_ISSUER)
    except jwt.PyJWTError:
        return None

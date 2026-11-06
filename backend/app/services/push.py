"""Web Push transport (FR-16). See docs/adr/ADR-007-web-push-notifications.md.

No account or third-party service is required: VAPID (RFC 8292) is a
self-issued identity, and the browser's own push service (Google's for
Chrome, Mozilla's for Firefox, Apple's for Safari) delivers the message to
the endpoint URL the browser handed out at subscribe time.

Kept separate from `app/services/notifications.py` (which decides *who*
gets notified and *what* the message says) so this module is a thin,
independently-testable transport: send one message, report success or a
typed failure.

References:
    - https://datatracker.ietf.org/doc/html/rfc8292 (VAPID)
    - https://pypi.org/project/pywebpush/
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException, webpush

from app.config import get_settings

logger = logging.getLogger(__name__)

_SEND_TIMEOUT_SECONDS = 5


class PushDeliveryError(Exception):
    """A push attempt failed. `gone` marks a subscription the browser itself
    revoked (404/410 from the push service) — the caller should delete it
    rather than retry it on the next publish. `status_code` is the push
    service's own HTTP status when there is one (None for a network/timeout
    error), so callers can recognise a specific status (e.g. 403, a VAPID
    signature mismatch — FR-137) without re-parsing `reason`."""

    def __init__(self, reason: str, *, gone: bool = False, status_code: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.gone = gone
        self.status_code = status_code


def is_configured() -> bool:
    """Whether the founder has set the VAPID keys (INBOX #5). Until then the
    feature is visible-but-inert, never a 500."""
    settings = get_settings()
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def public_key() -> str | None:
    """The key the frontend passes as `applicationServerKey`; None when not configured."""
    return get_settings().vapid_public_key if is_configured() else None


def send(*, endpoint: str, p256dh: str, auth: str, payload: dict) -> None:
    """Send one push message. Raises PushDeliveryError on any failure,
    including "not configured" — callers must check is_configured() first
    if they want to skip attempting sends entirely."""
    settings = get_settings()
    if not is_configured():
        raise PushDeliveryError("push notifications are not configured on this server")
    subscription_info = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=_SEND_TIMEOUT_SECONDS,
        )
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        gone = status_code in (404, 410)
        reason = f"push service returned {status_code}" if status_code else "push service unreachable"
        logger.warning("Push delivery failed via %s: %s", urlsplit(endpoint).hostname, reason)
        raise PushDeliveryError(reason, gone=gone, status_code=status_code) from exc
    except Exception as exc:  # noqa: BLE001 — network/timeout errors from `requests`, not worth enumerating
        # The class, not the text: `requests` errors quote the endpoint URL, a bearer capability for this person's pushes.
        reason = exc.__class__.__name__
        logger.warning("Push delivery failed via %s: %s", urlsplit(endpoint).hostname, reason)
        raise PushDeliveryError(reason) from exc


def generate_keypair() -> tuple[str, str]:
    """Return (public_key, private_key) as url-safe base64 strings.

    For a human to run once (backend/scripts/generate_vapid_keys.py) and
    paste into Fly secrets — never called by the running app itself, and
    the private key is never written to disk or the repo by this function.
    """
    vapid = Vapid()
    vapid.generate_keys()
    raw_public = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    raw_private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    return b64urlencode(raw_public), b64urlencode(raw_private)

"""Address to coordinates via OpenStreetMap Nominatim — free, keyless.

See ADR-006 for the usage-policy citation (1 req/s, a real User-Agent,
no bulk/autocomplete queries — none of which we do: one call per location
save). Every failure mode (timeout, network error, no match, malformed
response) returns None rather than raising, so a location always stays
editable even when the geocoder is down or the address doesn't resolve —
the dod's own "external call has a timeout and a fallback" requirement.

Reference: https://nominatim.org/release-docs/latest/api/Search/
"""

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_USER_AGENT = "FilmRunner/1.0 (+https://github.com/sandovabarbora/filmrunner)"
_TIMEOUT = 5.0


@dataclass
class GeocodeResult:
    lat: float
    lng: float
    display_name: str


def geocode(address: str) -> GeocodeResult | None:
    """Resolve a free-text address to coordinates and the resolved place
    name, or None if it can't be resolved or the geocoder is unreachable."""
    if not address or not address.strip():
        return None
    try:
        response = httpx.get(
            get_settings().nominatim_url,
            params={"q": address, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Only the class: an address is personal data, and httpx puts it in the message through the URL.
        logger.warning("Geocoding failed: %s", exc.__class__.__name__)
        return None

    if not results:
        return None
    top = results[0]
    try:
        return GeocodeResult(lat=float(top["lat"]), lng=float(top["lon"]), display_name=top["display_name"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Geocoding returned an unexpected shape: %s", exc.__class__.__name__)
        return None

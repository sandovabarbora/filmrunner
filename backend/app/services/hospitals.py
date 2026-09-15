"""Nearest hospital suggestion from coordinates, via the OpenStreetMap
Overpass API — free, keyless (see ADR-006). A suggestion the AD confirms
before it is saved on the location, never an autofill.

Reference: https://wiki.openstreetmap.org/wiki/Overpass_API
"""

import logging
import math

import httpx

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_TIMEOUT = 5.0
_RADIUS_METERS = 10_000


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_hospital_suggestion(lat: float, lng: float) -> str | None:
    """A "Name, address" suggestion for the closest hospital within 10km, or
    None if the provider is unreachable or nothing is found nearby."""
    query = (
        f"[out:json][timeout:5];"
        f'node["amenity"="hospital"](around:{_RADIUS_METERS},{lat},{lng});'
        f"out center 10;"
    )
    try:
        response = httpx.post(_OVERPASS_URL, data={"data": query}, timeout=_TIMEOUT)
        response.raise_for_status()
        elements = response.json().get("elements", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Nearest-hospital lookup failed for (%s, %s): %s", lat, lng, exc)
        return None

    candidates = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or "lat" not in el or "lon" not in el:
            continue
        distance = _haversine_km(lat, lng, el["lat"], el["lon"])
        candidates.append((distance, name, tags))
    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0])
    _, name, tags = candidates[0]
    address_parts = [tags.get(k) for k in ("addr:street", "addr:housenumber", "addr:city") if tags.get(k)]
    address = " ".join(address_parts)
    return f"{name}, {address}" if address else name

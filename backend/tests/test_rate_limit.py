"""FR-51 / ADR-008: the public endpoints are guarded per IP and per token; a crew on one Wi-Fi is not."""

import threading

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.ratelimit import INSTANCES, SlidingWindow

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


@pytest.fixture(autouse=True)
def _built(client: TestClient):
    client.get("/healthz")  # builds the middleware stack, which instantiates the limiter (conftest resets it per test)
    for m in INSTANCES:
        m.reset()


def test_sliding_window_counts_a_minute_and_then_forgets() -> None:
    w = SlidingWindow(limit=3)
    assert [w.hit("k", now=t)[0] for t in (0, 1, 2)] == [True, True, True]
    allowed, retry = w.hit("k", now=3)
    assert not allowed and 1 <= retry <= 60
    assert w.hit("k", now=61)[0] is True  # the first hit fell out of the window
    assert w.hit("other", now=3)[0] is True  # keys are independent


def test_per_ip_limit_on_public_routes_only(client: TestClient) -> None:
    limit = get_settings().public_rate_limit_per_ip
    for _ in range(limit):
        assert client.get("/api/v1/public/push/vapid-key", headers={"fly-client-ip": "203.0.113.9"}).status_code == 200
    r = client.get("/api/v1/public/push/vapid-key", headers={"fly-client-ip": "203.0.113.9"})
    assert r.status_code == 429 and r.headers["retry-after"].isdigit()
    # another client is not affected; authenticated routes and healthz are never limited
    assert client.get("/api/v1/public/push/vapid-key", headers={"fly-client-ip": "203.0.113.10"}).status_code == 200
    assert client.get("/healthz", headers={"fly-client-ip": "203.0.113.9"}).status_code == 200
    assert client.get("/api/v1/productions", headers={**AUTH, "fly-client-ip": "203.0.113.9"}).status_code == 200


def test_per_token_limit_stops_probing_before_the_ip_limit(client: TestClient) -> None:
    per_token = get_settings().public_rate_limit_per_token
    pid = client.post("/api/v1/productions", json={"name": "RL"}, headers=AUTH).json()["id"]
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
                        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH).json()
    ip = {"fly-client-ip": "198.51.100.7"}
    for i in range(per_token):
        assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/probe-token", headers=ip).status_code == 404
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/probe-token", headers=ip).status_code == 429
    # different bogus tokens each count for themselves until the IP limit; the 31st distinct token still passes here
    assert client.get("/api/v1/public/crew/another-token/next", headers=ip).status_code == 404


def test_a_whole_crew_on_one_wifi_gets_through(client: TestClient) -> None:
    """Failure case from the dod: 40 people × 5 requests each in a minute from one IP must not be throttled."""
    pid = client.post("/api/v1/productions", json={"name": "Wi-Fi"}, headers=AUTH).json()["id"]
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
                        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH).json()
    tokens = []
    for i in range(40):
        cid = client.post("/api/v1/contacts", json={"name": f"Crew {i}"}, headers=AUTH).json()["id"]
        tokens.append(client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "D", "position": "P"}, headers=AUTH).json()["personal_token"])
    ip = {"fly-client-ip": "192.0.2.44"}
    statuses = []
    for tok in tokens:
        statuses.append(client.get(f"/api/v1/public/crew/{tok}/next", headers=ip).status_code)
        statuses.append(client.get(f"/api/v1/public/call-sheets/{sheet['id']}", headers=ip).status_code)
        statuses.append(client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/{tok}", headers=ip).status_code)
        statuses.append(client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{tok}", headers=ip).status_code)
        statuses.append(client.get("/api/v1/public/push/vapid-key", headers=ip).status_code)
    assert 429 not in statuses and len(statuses) == 200


def test_concurrent_burst_flips_at_exactly_the_configured_threshold(client: TestClient) -> None:
    """FR-128 dod: a *concurrent* burst, not just a sequential one, must still find the real
    threshold — proves the sliding window's lock is actually race-free under real concurrency."""
    limit = get_settings().public_rate_limit_per_ip
    over = 50
    ip = {"fly-client-ip": "203.0.113.55"}
    results: list[int] = []
    lock = threading.Lock()

    def fire() -> None:
        status = client.get("/api/v1/public/push/vapid-key", headers=ip).status_code
        with lock:
            results.append(status)

    threads = [threading.Thread(target=fire) for _ in range(limit + over)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [200] * limit + [429] * over


def test_a_whole_crew_with_photos_on_one_wifi_gets_through(client: TestClient) -> None:
    """FR-128 failure case: FR-18 avatars mean the sheet's contact rows render an <img> per
    *other* crew member too, not one request per person — 40 crew all with a photo is up to
    ~40 photo fetches per device, ~1,600 from one office IP. Those must not share the functional
    per-IP budget, or a photo burst 429s the next device's real /seen or /me call."""
    pid = client.post("/api/v1/productions", json={"name": "Wi-Fi Photos"}, headers=AUTH).json()["id"]
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
                        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH).json()
    tokens, contact_ids = [], []
    jpeg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")  # minimal valid JPEG
    for i in range(40):
        cid = client.post("/api/v1/contacts", json={"name": f"Crew {i}"}, headers=AUTH).json()["id"]
        client.post(f"/api/v1/contacts/{cid}/photo", files={"file": ("a.jpg", jpeg, "image/jpeg")}, headers=AUTH)
        contact_ids.append(cid)
        tokens.append(client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "D", "position": "P"}, headers=AUTH).json()["personal_token"])
    ip = {"fly-client-ip": "192.0.2.77"}
    statuses = []
    for tok in tokens:
        statuses.append(client.get(f"/api/v1/public/crew/{tok}/next", headers=ip).status_code)
        statuses.append(client.get(f"/api/v1/public/call-sheets/{sheet['id']}", headers=ip).status_code)
        statuses.append(client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/{tok}", headers=ip).status_code)
        statuses.append(client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{tok}", headers=ip).status_code)
        statuses.append(client.get("/api/v1/public/push/vapid-key", headers=ip).status_code)
        for cid in contact_ids:  # the sheet renders every other crew member's avatar on load
            statuses.append(client.get(f"/api/v1/public/contacts/{cid}/photo", headers=ip).status_code)
    assert len(statuses) == 40 * (5 + 40)
    assert 429 not in statuses

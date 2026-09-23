"""FR-72: measure publish latency with a pilot-scale number of push
subscribers, closing (or being honest about not closing) the revisit
trigger `docs/adr/ADR-007-web-push-notifications.md:147-149` names for
itself: "revisit if a production's crew count makes publish latency
noticeable".

Two separate things are measured here, on purpose:

1. The same-process overhead of the delivery loop itself (ORM queries,
   payload construction, one `DistributionLog` row per subscriber, one
   commit) with `app.services.push.webpush` mocked to return instantly.
   This is representative of what this codebase's own code contributes,
   but NOT of a real network round trip.
2. What the loop looks like if each `webpush()` call carries a delay
   that stands in for a real HTTPS POST to a push service. This
   sandbox has no live push service and no real subscribed device
   (every prior FR-16 shift note says the same), so there is no
   measured real-world round-trip time to plug in here; a `WebSearch`
   this shift for a published "typical" Web Push endpoint latency
   figure came back with nothing more specific than "under one
   second" (IETF webpush-protocol draft's push-window discussion) —
   not a number worth treating as fact. The delay used below
   (`_ASSUMED_ROUND_TRIP_SECONDS`) is stated as an assumption, not a
   measurement, chosen as the low end of an ordinary synchronous
   HTTPS POST (connection + TLS + request + response) on a reasonable
   network — the same order of magnitude this module's own
   `_SEND_TIMEOUT_SECONDS = 5` treats as a generous upper bound.

This is the dod's own failure case: the mocked transport genuinely
cannot produce a trustworthy absolute number, so this test reports
both figures honestly, labelled, rather than presenting either as a
verified real-world measurement.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.models.production import Contact, CrewMember, Production
from app.models.push import PushSubscription

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}

SUBSCRIBER_COUNT = 50  # within the dod's named 40-60 range

# Stated assumption, not a measurement — see module docstring. Chosen as a
# conservative *low* estimate for one synchronous HTTPS POST, so the
# resulting total is itself a floor, not a worst case.
_ASSUMED_ROUND_TRIP_SECONDS = 0.15


@pytest.fixture()
def vapid_configured(monkeypatch):
    from app.services import push as push_service

    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", push_service.generate_keypair()[1])
    return settings


def _seed_production_with_subscribers(db_session, count: int) -> uuid.UUID:
    """Direct ORM inserts, not the API — the thing under measurement is
    `publish_revision`'s notification loop, not crew-setup HTTP overhead."""
    production = Production(name="Push Scale Co")
    db_session.add(production)
    db_session.flush()

    for i in range(count):
        contact = Contact(name=f"Crew Member {i}", phone=f"+420 700 000 {i:03d}")
        db_session.add(contact)
        db_session.flush()
        member = CrewMember(
            production_id=production.id, contact_id=contact.id,
            department="Grip", position="Grip",
        )
        db_session.add(member)
        db_session.flush()
        db_session.add(
            PushSubscription(
                crew_member_id=member.id,
                endpoint=f"https://push.example.com/ep{i}",
                p256dh="BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA",
                auth="fake-auth-key",
                link_url="https://filmrunner.example/?sheet=abc&api=https://api.example",
            )
        )
    db_session.commit()
    return production.id


class TestPublishLatencyAtPilotScale:
    def test_instant_transport_measures_only_this_codebases_own_overhead(
        self, client: TestClient, db_session, vapid_configured
    ) -> None:
        """Lower bound: ORM + payload + logging overhead with the network
        call itself replaced by a no-op. Confirms the delivery loop's own
        code is not the bottleneck, independent of network latency."""
        pid = _seed_production_with_subscribers(db_session, SUBSCRIBER_COUNT)

        with patch("app.services.push.webpush") as mock_webpush:
            mock_webpush.return_value = None
            start = time.perf_counter()
            resp = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-30", "day_number": 1, "day_count": 1,
                      "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            )
            elapsed = time.perf_counter() - start

        assert resp.status_code == 201, resp.text
        notifications = resp.json()["current_revision"]["notifications"]
        assert notifications == {"attempted": SUBSCRIBER_COUNT, "delivered": SUBSCRIBER_COUNT, "failed": []}
        assert mock_webpush.call_count == SUBSCRIBER_COUNT

        # This is the number that would be "falsely reassuring" if reported
        # alone as "publish latency at pilot scale": it excludes the one
        # thing (network I/O to a real push service) the revisit trigger
        # is actually about.
        print(f"\n[FR-72] instant-transport overhead for {SUBSCRIBER_COUNT} subscribers: {elapsed * 1000:.1f} ms")
        assert elapsed < 2.0, (
            f"This codebase's own per-subscriber overhead (DB writes, payload, logging) took "
            f"{elapsed:.3f}s for {SUBSCRIBER_COUNT} subscribers, unexpectedly slow even with the "
            f"network call mocked out — that would be a real regression worth its own item."
        )

    def test_assumed_network_delay_projects_a_noticeable_total(
        self, client: TestClient, db_session, vapid_configured
    ) -> None:
        """Upper-bound-of-a-lower-bound: same loop, `webpush()` now sleeps for
        `_ASSUMED_ROUND_TRIP_SECONDS` per call to stand in for a real HTTPS
        POST. This is not a measurement of a real push service — see the
        module docstring — but it is the only way to reason about the
        trigger's actual question (does crew count make latency noticeable)
        without either a live push service or a real pilot crew, neither of
        which exists in this environment."""
        pid = _seed_production_with_subscribers(db_session, SUBSCRIBER_COUNT)

        def _slow_webpush(**kwargs):
            time.sleep(_ASSUMED_ROUND_TRIP_SECONDS)

        with patch("app.services.push.webpush", side_effect=_slow_webpush):
            start = time.perf_counter()
            resp = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-30", "day_number": 1, "day_count": 1,
                      "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            )
            elapsed = time.perf_counter() - start

        assert resp.status_code == 201, resp.text
        expected_floor = SUBSCRIBER_COUNT * _ASSUMED_ROUND_TRIP_SECONDS
        print(
            f"\n[FR-72] projected serial publish latency for {SUBSCRIBER_COUNT} subscribers "
            f"at an assumed {_ASSUMED_ROUND_TRIP_SECONDS * 1000:.0f} ms/request: {elapsed:.2f}s "
            f"(assumption, not a live measurement — see module docstring)"
        )
        # The loop is serial by construction (app/services/notifications.py
        # `_notify`), so elapsed must scale with count * per-call delay,
        # not stay flat — this is the actual mechanism the revisit trigger
        # is asking about, demonstrated rather than asserted from reading
        # the code.
        assert elapsed >= expected_floor

"""FR-72 measured publish latency with a pilot-scale number of push
subscribers and found it serial and synchronous with the HTTP response
(~7.7s projected for 50 subscribers) — filed as FR-78. FR-78 moved delivery
onto a FastAPI `BackgroundTasks` job that runs after the response is already
on its way back to the AD (app/routers/call_sheets.py, app/services/
notifications.py's *_in_background wrappers).

Three things are measured here, on purpose:

1. The same-process overhead of the delivery loop itself (ORM queries,
   payload construction, one `DistributionLog` row per subscriber, one
   commit) with `app.services.push.webpush` mocked to return instantly.
   This is representative of what this codebase's own code contributes,
   but NOT of a real network round trip.
2. What the loop looks like if each `webpush()` call carries a delay that
   stands in for a real HTTPS POST to a push service. This sandbox has no
   live push service and no real subscribed device (every prior FR-16 shift
   note says the same), so there is no measured real-world round-trip time
   to plug in here; a `WebSearch` this shift for a published "typical" Web
   Push endpoint latency figure came back with nothing more specific than
   "under one second" (IETF webpush-protocol draft's push-window
   discussion) — not a number worth treating as fact. The delay used below
   (`_ASSUMED_ROUND_TRIP_SECONDS`) is stated as an assumption, not a
   measurement, chosen as the low end of an ordinary synchronous HTTPS POST
   (connection + TLS + request + response) on a reasonable network — the
   same order of magnitude this module's own `_SEND_TIMEOUT_SECONDS = 5`
   treats as a generous upper bound.
3. FR-78's own claim — that the *endpoint function itself* returns without
   waiting on that delay, and only running the background task afterward
   pays it. Verified directly below by calling the router function (not
   through TestClient/HTTP): FastAPI's `TestClient` drives the whole ASGI
   request, background tasks included, to completion inside one blocking
   call (confirmed by reading `httpx`'s `ASGITransport.handle_async_request`,
   which `await`s the app in full), so it cannot by itself show a wall-clock
   difference between "response sent" and "delivery finished" — a real
   deployed server already has the HTTP response on the wire to the AD's
   phone before the background task starts, but nothing observable through
   TestClient's blocking `.post()` call marks that moment. Driving the
   endpoint function directly with our own `BackgroundTasks()` instance
   does: we can inspect it, unexecuted, right after the function returns.

This is the dod's own failure case: the mocked transport genuinely cannot
produce a trustworthy absolute number for (1) and (2), so this test reports
both figures honestly, labelled, rather than presenting either as a
verified real-world measurement.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.background import BackgroundTasks

from app.auth import Principal
from app.config import get_settings
from app.models.call_sheet import DistributionChannel, DistributionLog
from app.models.production import Contact, CrewMember, Production
from app.models.push import PushSubscription
from app.routers.call_sheets import publish_revision_endpoint
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate
from app.services.call_sheets import create_call_sheet

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
SERVICE_PRINCIPAL = Principal(kind="service", subject="service", email=None)

# FR-78: delivery runs in a background task with its own DB session; see
# conftest.py's background_tasks_share_db for why these tests need it.
pytestmark = pytest.mark.usefixtures("background_tasks_share_db")

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


def _distribution_log_rows(db_session) -> list[DistributionLog]:
    return db_session.query(DistributionLog).filter(DistributionLog.channel == DistributionChannel.PUSH).all()


class TestPublishLatencyAtPilotScale:
    def test_instant_transport_measures_only_this_codebases_own_overhead(
        self, client: TestClient, db_session, vapid_configured
    ) -> None:
        """Lower bound: ORM + payload + logging overhead with the network
        call itself replaced by a no-op. Confirms the delivery loop's own
        code is not the bottleneck, independent of network latency. Since
        FR-78, this total also includes the background task itself (see the
        module docstring on why TestClient can't separate the two) — still a
        legitimate regression check on the loop's own overhead."""
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
        rows = _distribution_log_rows(db_session)
        assert len(rows) == SUBSCRIBER_COUNT and all(row.error is None for row in rows)
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
        which exists in this environment.

        Since FR-78 this total is no longer what the AD's phone experiences —
        TestClient still pays the delay inside its one blocking `.post()`
        call (see the module docstring) — but the delay itself is unchanged
        and still worth confirming exists; `test_endpoint_returns_before_the_
        background_task_runs` below is what actually proves it moved."""
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
            f"\n[FR-72] projected serial delivery latency for {SUBSCRIBER_COUNT} subscribers "
            f"at an assumed {_ASSUMED_ROUND_TRIP_SECONDS * 1000:.0f} ms/request: {elapsed:.2f}s "
            f"(assumption, not a live measurement — see module docstring; still inside the blocking "
            f"TestClient call — see test_endpoint_returns_before_the_background_task_runs for the "
            f"response/delivery split FR-78 actually delivers)"
        )
        # The delivery loop is still serial by construction (app/services/notifications.py
        # `_notify`), so total delivery time must scale with count * per-call delay, not stay
        # flat — unchanged by FR-78, which moved *when* this cost is paid, not its size.
        assert elapsed >= expected_floor

    def test_endpoint_returns_before_the_background_task_runs(self, db_session, vapid_configured) -> None:
        """FR-78's actual claim, proven directly: call the router function itself
        (not through TestClient/HTTP — see the module docstring for why that
        can't show this) with our own BackgroundTasks(). The slow delivery
        loop above must not have run at all by the time the endpoint returns
        — only queued — and must actually run, and take the full projected
        time, once something (a real server, here the test) executes it."""
        pid = _seed_production_with_subscribers(db_session, SUBSCRIBER_COUNT)
        call_sheet = create_call_sheet(
            db_session, pid,
            CallSheetCreate(shoot_date=date(2026, 9, 30), day_number=1, day_count=1,
                            initial_revision=CallSheetRevisionCreate(general_crew_call="06:30", schedule_items=[])),
            created_by="service:test",
        )

        def _slow_webpush(**kwargs):
            time.sleep(_ASSUMED_ROUND_TRIP_SECONDS)

        background_tasks = BackgroundTasks()
        with patch("app.services.push.webpush", side_effect=_slow_webpush) as mock_webpush:
            start = time.perf_counter()
            revision = publish_revision_endpoint(
                call_sheet.id,
                CallSheetRevisionCreate(general_crew_call="07:00", schedule_items=[]),
                background_tasks,
                db=db_session,
                principal=SERVICE_PRINCIPAL,
            )
            endpoint_elapsed = time.perf_counter() - start

            # The endpoint returned; nothing has been sent yet, only queued.
            assert mock_webpush.call_count == 0
            assert len(background_tasks.tasks) == 1
            assert _distribution_log_rows(db_session) == []

            start = time.perf_counter()
            asyncio.run(background_tasks())  # what a real server runs after the response is already on the wire
            background_elapsed = time.perf_counter() - start

        assert revision.revision_letter == "B"
        assert mock_webpush.call_count == SUBSCRIBER_COUNT
        assert len(_distribution_log_rows(db_session)) == SUBSCRIBER_COUNT
        print(
            f"\n[FR-78] endpoint returned in {endpoint_elapsed * 1000:.1f} ms; "
            f"background delivery took {background_elapsed:.2f}s for {SUBSCRIBER_COUNT} subscribers"
        )
        assert endpoint_elapsed < 0.5, "publish_revision_endpoint itself must not scale with subscriber count any more"
        assert background_elapsed >= SUBSCRIBER_COUNT * _ASSUMED_ROUND_TRIP_SECONDS  # the cost still exists — it just moved

"""FR-16: Web Push subscribe/unsubscribe and revision-publish notifications.

`pywebpush`'s actual network call is mocked (no real push service in
tests), but the VAPID signing path (app/services/push.py calling into
py_vapid) runs for real — see test_send_signs_and_calls_webpush_for_real.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pywebpush import WebPushException

from app.config import get_settings
from app.models.call_sheet import CallSheet, CallSheetRevision, DistributionChannel, DistributionLog
from app.models.push import PushSubscription
from app.services import push as push_service
from app.services.notifications import notify_subscribers

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}

# FR-78: delivery now happens in a background task with its own DB session;
# see conftest.py's background_tasks_share_db for why tests need this to
# observe what it wrote.
pytestmark = pytest.mark.usefixtures("background_tasks_share_db")


@pytest.fixture()
def vapid_configured(monkeypatch):
    """Simulate the founder having set the two Fly secrets (INBOX #5)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", push_service.generate_keypair()[1])
    return settings


def _setup(client: TestClient):
    pid = client.post("/api/v1/productions", json={"name": "Push Co"}, headers=AUTH).json()["id"]
    contact = client.post("/api/v1/contacts", json={"name": "Jana Novotná", "phone": "+420 111 222 333"}, headers=AUTH).json()["id"]
    member = client.post(
        f"/api/v1/productions/{pid}/crew-members",
        json={"contact_id": contact, "department": "Grip", "position": "Key grip"},
        headers=AUTH,
    ).json()
    return pid, member


def _notifications(client: TestClient, call_sheet_id: str) -> dict | None:
    """FR-78: the delivery summary moved from the publish response to the
    history panel, backed by the same DistributionLog rows."""
    history = client.get(f"/api/v1/call-sheets/{call_sheet_id}/history", headers=AUTH).json()
    return history[-1]["notifications"]


def _subscribe_payload(endpoint="https://push.example.com/ep1"):
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"},
        "link_url": "https://filmrunner.example/?sheet=abc&api=https://api.example&me=tok",
    }


class TestVapidKeyEndpoint:
    def test_public_key_is_null_when_not_configured(self, client: TestClient) -> None:
        resp = client.get("/api/v1/public/push/vapid-key")
        assert resp.status_code == 200
        assert resp.json() == {"public_key": None}

    def test_public_key_is_returned_once_configured(self, client: TestClient, vapid_configured) -> None:
        resp = client.get("/api/v1/public/push/vapid-key")
        assert resp.json() == {"public_key": "test-public-key"}


class TestSubscribe:
    def test_subscribe_creates_a_subscription(self, client: TestClient, db_session) -> None:
        pid, member = _setup(client)
        resp = client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())
        assert resp.status_code == 201, resp.text
        rows = db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).all()
        assert len(rows) == 1
        assert rows[0].endpoint == "https://push.example.com/ep1"

    def test_subscribe_with_unknown_token_is_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/public/crew/not-a-real-token/push-subscription", json=_subscribe_payload())
        assert resp.status_code == 404

    def test_resubscribing_the_same_endpoint_updates_in_place(self, client: TestClient, db_session) -> None:
        pid, member = _setup(client)
        payload = _subscribe_payload()
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=payload)
        payload["keys"]["auth"] = "rotated-auth-key"
        resp = client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=payload)
        assert resp.status_code == 201
        rows = db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).all()
        assert len(rows) == 1
        assert rows[0].auth == "rotated-auth-key"

    def test_unsubscribe_removes_the_subscription(self, client: TestClient, db_session) -> None:
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())
        resp = client.request(
            "DELETE",
            f"/api/v1/public/crew/{member['personal_token']}/push-subscription",
            params={"endpoint": "https://push.example.com/ep1"},
        )
        assert resp.status_code == 204
        rows = db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).all()
        assert rows == []


class TestNotifySubscribers:
    def test_no_subscribers_is_a_silent_no_op(self, client: TestClient, db_session, vapid_configured) -> None:
        pid, member = _setup(client)
        sheet = client.post(
            f"/api/v1/productions/{pid}/call-sheets",
            json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
            headers=AUTH,
        ).json()
        assert _notifications(client, sheet["id"]) is None  # no subscribers: no DistributionLog row, not a zeroed summary

    def test_not_configured_is_a_silent_no_op_even_with_subscribers(self, client: TestClient) -> None:
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())
        sheet = client.post(
            f"/api/v1/productions/{pid}/call-sheets",
            json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
            headers=AUTH,
        ).json()
        assert _notifications(client, sheet["id"]) is None

    def test_successful_delivery_is_logged(self, client: TestClient, db_session, vapid_configured) -> None:
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())
        with patch("app.services.push.webpush") as mock_webpush:
            mock_webpush.return_value = None
            sheet = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            ).json()
        assert _notifications(client, sheet["id"]) == {"attempted": 1, "delivered": 1, "failed": []}
        assert mock_webpush.call_count == 1
        assert mock_webpush.call_args.kwargs["data"]
        assert "New call sheet: crew call 06:30" in mock_webpush.call_args.kwargs["data"]
        logs = db_session.query(DistributionLog).filter(DistributionLog.channel == DistributionChannel.PUSH).all()
        assert len(logs) == 1 and logs[0].sent_at is not None and logs[0].error is None

    def test_replaces_note_on_a_second_revision(self, client: TestClient, db_session, vapid_configured) -> None:
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())
        with patch("app.services.push.webpush"):
            sheet = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            ).json()
            with patch("app.services.push.webpush") as mock_webpush:
                client.post(
                    f"/api/v1/call-sheets/{sheet['id']}/revisions",
                    json={"general_crew_call": "07:00", "schedule_items": []},
                    headers=AUTH,
                )
        assert json.loads(mock_webpush.call_args.kwargs["data"])["body"] == "REV B replaces A: crew call 06:30 → 07:00"

    def test_failed_delivery_is_logged_per_crew_member_and_publish_still_succeeds(self, client: TestClient, db_session, vapid_configured) -> None:
        """The dod's own failure case: a push that cannot be delivered must not
        block the publish, and must be visible per crew member, not silently swallowed."""
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())

        class _FakeResponse:
            status_code = 500
            text = "internal error"

        with patch("app.services.push.webpush", side_effect=WebPushException("boom", response=_FakeResponse())):
            resp = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            )
        assert resp.status_code == 201  # publish itself is not blocked by a notification failure
        notifications = _notifications(client, resp.json()["id"])
        assert notifications["delivered"] == 0
        assert notifications["failed"] == [{"crew_member_name": "Jana Novotná", "reason": "push service returned 500"}]
        logs = db_session.query(DistributionLog).filter(DistributionLog.channel == DistributionChannel.PUSH).all()
        assert len(logs) == 1 and logs[0].sent_at is None and logs[0].error == "push service returned 500"
        # A transient failure keeps the subscription for the next revision.
        assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).count() == 1

    def test_a_single_403_is_not_misclassified_as_a_key_rotation(self, client: TestClient, db_session, vapid_configured) -> None:
        """FR-137's dod, step 1: document what the code does with a plain 403
        today, before any fix — `gone` stays False (push.py:77 only treats
        404/410 as gone), so nothing deletes the subscription on a single 403."""

        class _ForbiddenResponse:
            status_code = 403
            text = "forbidden"

        with patch("app.services.push.webpush", side_effect=WebPushException("forbidden", response=_ForbiddenResponse())):
            with pytest.raises(push_service.PushDeliveryError) as exc_info:
                push_service.send(endpoint="https://push.example.com/ep1", p256dh="a", auth="b", payload={})
        assert exc_info.value.gone is False
        assert exc_info.value.status_code == 403

    def test_a_single_403_is_logged_as_a_plain_failure(self, client: TestClient, db_session, vapid_configured) -> None:
        """One 403 alone must not be flagged as a key rotation (the dod's own
        failure case) — it reads the same as any other transient failure."""
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())

        class _ForbiddenResponse:
            status_code = 403
            text = "forbidden"

        with patch("app.services.push.webpush", side_effect=WebPushException("forbidden", response=_ForbiddenResponse())):
            resp = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            )
        logs = db_session.query(DistributionLog).filter(DistributionLog.channel == DistributionChannel.PUSH).all()
        assert len(logs) == 1 and logs[0].error == "push service returned 403"
        assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).one().consecutive_403_count == 1

    def test_a_repeated_403_from_the_same_subscription_is_flagged_as_likely_key_rotation(
        self, client: TestClient, db_session, vapid_configured
    ) -> None:
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())

        class _ForbiddenResponse:
            status_code = 403
            text = "forbidden"

        def _publish(day_number: int, call: str):
            return client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": day_number, "day_count": 1, "initial_revision": {"general_crew_call": call, "schedule_items": []}},
                headers=AUTH,
            )

        with patch("app.services.push.webpush", side_effect=WebPushException("forbidden", response=_ForbiddenResponse())):
            _publish(1, "06:30")
            _publish(2, "07:00")

        logs = (
            db_session.query(DistributionLog)
            .join(CallSheetRevision, CallSheetRevision.id == DistributionLog.revision_id)
            .join(CallSheet, CallSheet.id == CallSheetRevision.call_sheet_id)
            .filter(DistributionLog.channel == DistributionChannel.PUSH)
            .order_by(CallSheet.day_number)  # publish order; ids are random UUIDs, so ordering by id was a coin flip
            .all()
        )
        assert len(logs) == 2
        assert logs[0].error == "push service returned 403"
        assert "repeated" in logs[1].error and "VAPID" in logs[1].error
        assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).one().consecutive_403_count == 2

    def test_a_successful_send_resets_the_403_counter(self, client: TestClient, db_session, vapid_configured) -> None:
        """A 403 that clears on the next attempt was transient, not a key
        rotation — the counter must not keep accumulating across a success."""
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())

        class _ForbiddenResponse:
            status_code = 403
            text = "forbidden"

        with patch("app.services.push.webpush", side_effect=WebPushException("forbidden", response=_ForbiddenResponse())):
            sheet = client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            ).json()
        with patch("app.services.push.webpush", return_value=None):
            client.post(
                f"/api/v1/call-sheets/{sheet['id']}/revisions",
                json={"general_crew_call": "07:00", "schedule_items": []},
                headers=AUTH,
            )

        assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).one().consecutive_403_count == 0

    def test_a_revoked_subscription_is_deleted_so_it_is_not_retried(self, client: TestClient, db_session, vapid_configured) -> None:
        pid, member = _setup(client)
        client.post(f"/api/v1/public/crew/{member['personal_token']}/push-subscription", json=_subscribe_payload())

        class _GoneResponse:
            status_code = 410
            text = "gone"

        with patch("app.services.push.webpush", side_effect=WebPushException("gone", response=_GoneResponse())):
            client.post(
                f"/api/v1/productions/{pid}/call-sheets",
                json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
                headers=AUTH,
            )
        assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == member["id"]).count() == 0


class TestPersonalPush:
    """FR-201: each phone gets its own line, and nobody is woken by someone else's call moving."""

    def _two_subscribers(self, client: TestClient):
        pid, gaffer = _setup(client)
        contact = client.post("/api/v1/contacts", json={"name": "Marek Sýkora"}, headers=AUTH).json()["id"]
        dop = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "Camera", "position": "DoP"}, headers=AUTH).json()
        client.post(f"/api/v1/public/crew/{gaffer['personal_token']}/push-subscription", json=_subscribe_payload("https://push.example.com/gaffer"))
        client.post(f"/api/v1/public/crew/{dop['personal_token']}/push-subscription", json=_subscribe_payload("https://push.example.com/dop"))
        sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": "2026-11-10", "day_number": 7, "day_count": 24, "initial_revision": {"general_crew_call": "07:00", "schedule_items": []}}, headers=AUTH).json()
        return gaffer, sheet

    @staticmethod
    def _bodies(mocked) -> dict[str, str]:
        return {c.kwargs["subscription_info"]["endpoint"].rsplit("/", 1)[1]: json.loads(c.kwargs["data"])["body"] for c in mocked.call_args_list}

    def test_only_the_person_whose_call_moved_is_told(self, client: TestClient, vapid_configured) -> None:
        gaffer, sheet = self._two_subscribers(client)
        with patch.object(push_service, "webpush") as mocked:
            client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": [], "crew_calls": [{"crew_member_id": gaffer["id"], "call_time": "05:00"}]}, headers=AUTH)
        bodies = self._bodies(mocked)
        assert set(bodies) == {"gaffer"}
        assert bodies["gaffer"].startswith("REV B replaces A: your call 07:00 → 05:00")

    def test_a_change_for_everyone_reaches_everyone_and_leads_with_their_own(self, client: TestClient, vapid_configured) -> None:
        gaffer, sheet = self._two_subscribers(client)
        with patch.object(push_service, "webpush") as mocked:
            client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "06:30", "schedule_items": [], "crew_calls": [{"crew_member_id": gaffer["id"], "call_time": "05:00"}]}, headers=AUTH)
        bodies = self._bodies(mocked)
        assert bodies["gaffer"].startswith("REV B replaces A: your call 07:00 → 05:00; crew call 07:00 → 06:30")
        assert bodies["dop"].startswith("REV B replaces A: crew call 07:00 → 06:30")  # the same move, said once

    def test_republishing_identical_content_still_tells_everyone(self, client: TestClient, vapid_configured) -> None:
        """A restored cancelled day is published unchanged, and that is the message that says the day is back on."""
        _gaffer, sheet = self._two_subscribers(client)
        with patch.object(push_service, "webpush") as mocked:
            client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "07:00", "schedule_items": []}, headers=AUTH)
        assert set(self._bodies(mocked)) == {"gaffer", "dop"}


def test_send_signs_and_calls_webpush_for_real(vapid_configured, monkeypatch) -> None:
    """Exercises the real VAPID signing path (py_vapid), mocking only the final HTTP POST."""
    captured = {}

    def _fake_webpush(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(push_service, "webpush", _fake_webpush)
    push_service.send(
        endpoint="https://push.example.com/real", p256dh="fake-p256dh", auth="fake-auth",
        payload={"title": "t", "body": "b", "url": "https://example.com"},
    )
    assert captured["vapid_private_key"] == vapid_configured.vapid_private_key
    assert captured["vapid_claims"]["sub"] == vapid_configured.vapid_subject


def test_send_without_configuration_raises() -> None:
    with pytest.raises(push_service.PushDeliveryError):
        push_service.send(endpoint="https://x", p256dh="a", auth="b", payload={})

"""FR-185: DELETE /productions/{id} removes a production and every row scoped to it."""

import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.config import get_settings
from app.models.call_sheet import CallSheetRevision, CastCallEntry, CrewCallEntry, DistributionLog, ScheduleItem
from app.models.membership import ProductionMember
from app.models.production import CastMember, Contact, CrewMember, Location, Production
from app.models.push import PushSubscription
from app.models.seen import RevisionView
from app.services import push as push_service

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}

# FR-78: notification delivery (and the DistributionLog row it writes) runs in a
# background task with its own DB session; see conftest.py's background_tasks_share_db.
pytestmark = pytest.mark.usefixtures("background_tasks_share_db")


@pytest.fixture()
def vapid_configured(monkeypatch):
    """Simulate the founder having set the two Fly secrets (INBOX #5), so a
    publish actually attempts delivery and logs a DistributionLog row."""
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", push_service.generate_keypair()[1])
    return settings


@pytest.fixture()
def users(monkeypatch: pytest.MonkeyPatch):
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()

    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token: str):
            class Key:
                key = public
            return Key()

    monkeypatch.setattr(auth, "_jwk_client", lambda: FakeJwkClient())

    def headers(email: str) -> dict[str, str]:
        now = int(time.time())
        token = jwt.encode({"sub": f"uid-{email}", "email": email, "aud": "authenticated", "iat": now, "exp": now + 600}, private, algorithm="ES256")
        return {"Authorization": f"Bearer {token}"}

    return headers


def _build(client: TestClient) -> dict:
    """One production with at least one row of every type the delete must touch,
    plus a contact (cast) also used on a second, untouched production, so the
    orphan-contact cleanup can be checked both ways (deleted vs. kept)."""
    pid = client.post("/api/v1/productions", json={"name": "Delete me"}, headers=AUTH).json()["id"]
    c_crew = client.post("/api/v1/contacts", json={"name": "Petr Crew", "phone": "+420 1"}, headers=AUTH).json()["id"]
    c_cast = client.post("/api/v1/contacts", json={"name": "Anna Cast", "phone": "+420 2"}, headers=AUTH).json()["id"]
    hod = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": c_crew, "department": "AD", "position": "1st AD"}, headers=AUTH).json()
    actor = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": c_cast, "character_name": "MARTA"}, headers=AUTH).json()
    loc = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Troja", "address": None}, headers=AUTH).json()
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "viewer@example.com", "role": "viewer"}, headers=AUTH)

    push_resp = client.post(
        f"/api/v1/public/crew/{hod['personal_token']}/push-subscription",
        json={
            "endpoint": "https://push.example.com/delprod",
            "keys": {"p256dh": "BFakeP256dhKeyBFakeP256dhKeyBFakeP256dhKeyAA", "auth": "fake-auth-key"},
            "link_url": "https://filmrunner.example/?sheet=abc&api=https://api.example&me=tok",
        },
    )
    assert push_resp.status_code == 201, push_resp.text

    with patch("app.services.push.webpush") as mock_webpush:
        mock_webpush.return_value = None
        day = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
            "shoot_date": "2026-09-23", "day_number": 1, "day_count": 1, "initial_revision": {
                "general_crew_call": "06:30", "head_of_day_crew_member_id": hod["id"],
                "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "EXT", "day_night": "DAY", "set_description": "RIVERBANK", "page_count_eighths": 8, "location_id": loc["id"]}],
                "cast_calls": [{"cast_member_id": actor["id"], "status_code": "SW", "call_time": "06:00"}],
                "crew_calls": [{"crew_member_id": hod["id"], "call_time": "05:15"}],
            }}, headers=AUTH).json()
    assert mock_webpush.call_count == 1  # proves a real DistributionLog row was written, not skipped as unconfigured

    seen_resp = client.post(f"/api/v1/public/call-sheets/{day['id']}/seen/{hod['personal_token']}")
    assert seen_resp.status_code == 204, seen_resp.text

    # A second production reusing the cast contact: it must survive the first production's deletion.
    other_pid = client.post("/api/v1/productions", json={"name": "Keep me"}, headers=AUTH).json()["id"]
    client.post(f"/api/v1/productions/{other_pid}/cast-members", json={"contact_id": c_cast, "character_name": "MARTA 2"}, headers=AUTH)

    return {
        "pid": pid, "other_pid": other_pid, "c_crew": c_crew, "c_cast": c_cast,
        "hod_id": hod["id"], "actor_id": actor["id"], "location_id": loc["id"], "call_sheet_id": day["id"],
        "revision_id": day["current_revision"]["id"],
    }


def test_delete_production_removes_every_scoped_row(client: TestClient, db_session, vapid_configured) -> None:
    ids = _build(client)
    pid = ids["pid"]

    resp = client.delete(f"/api/v1/productions/{pid}", headers=AUTH)
    assert resp.status_code == 204, resp.text

    assert client.get(f"/api/v1/productions/{pid}", headers=AUTH).status_code == 404
    assert db_session.get(Production, pid) is None
    assert db_session.query(CrewMember).filter(CrewMember.production_id == pid).count() == 0
    assert db_session.query(CastMember).filter(CastMember.production_id == pid).count() == 0
    assert db_session.query(Location).filter(Location.production_id == pid).count() == 0
    assert db_session.query(ProductionMember).filter(ProductionMember.production_id == pid).count() == 0
    assert db_session.query(CallSheetRevision).filter(CallSheetRevision.id == ids["revision_id"]).count() == 0
    assert db_session.query(ScheduleItem).filter(ScheduleItem.revision_id == ids["revision_id"]).count() == 0
    assert db_session.query(CastCallEntry).filter(CastCallEntry.revision_id == ids["revision_id"]).count() == 0
    assert db_session.query(CrewCallEntry).filter(CrewCallEntry.revision_id == ids["revision_id"]).count() == 0
    assert db_session.query(DistributionLog).filter(DistributionLog.revision_id == ids["revision_id"]).count() == 0
    assert db_session.query(RevisionView).filter(RevisionView.crew_member_id == ids["hod_id"]).count() == 0
    assert db_session.query(PushSubscription).filter(PushSubscription.crew_member_id == ids["hod_id"]).count() == 0

    # The crew-only contact is now orphaned and gone; the cast contact survives via "Keep me".
    assert db_session.get(Contact, ids["c_crew"]) is None
    assert db_session.get(Contact, ids["c_cast"]) is not None
    assert client.get(f"/api/v1/productions/{ids['other_pid']}/cast-members", headers=AUTH).json()[0]["contact"]["id"] == ids["c_cast"]


def test_delete_production_is_owner_only(client: TestClient, users) -> None:
    owner, editor, viewer = users("owner@example.com"), users("editor@example.com"), users("viewer@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Owner only"}, headers=owner).json()["id"]
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "editor@example.com", "role": "editor"}, headers=owner)
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "viewer@example.com", "role": "viewer"}, headers=owner)

    assert client.delete(f"/api/v1/productions/{pid}", headers=viewer).status_code == 403
    assert client.delete(f"/api/v1/productions/{pid}", headers=editor).status_code == 403
    assert client.delete(f"/api/v1/productions/{pid}", headers=owner).status_code == 204


def test_delete_unknown_production_is_404(client: TestClient) -> None:
    import uuid
    assert client.delete(f"/api/v1/productions/{uuid.uuid4()}", headers=AUTH).status_code == 404

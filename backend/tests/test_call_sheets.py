"""Tests for production/call-sheet CRUD and the revision-publishing logic.

Covers the happy path, the 401 without a token, 404s, and the specific
domain invariant this skeleton exists to get right: publishing a new
revision must supersede the prior one, and the 27th revision on one day
must be rejected rather than silently corrupted (26-letter limit).
"""

import uuid

import pytest

from app.models.call_sheet import CallSheet, CallSheetRevision
from app.services.call_sheets import create_call_sheet, publish_revision
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate


def _minimal_call_sheet_payload(**overrides) -> CallSheetCreate:
    defaults = dict(
        shoot_date="2026-10-01",
        day_number=1,
        day_count=20,
        unit_name="Main Unit",
        initial_revision=CallSheetRevisionCreate(general_crew_call="06:00"),
    )
    defaults.update(overrides)
    return CallSheetCreate(**defaults)


def _create_production(client, auth_headers, name="Test Production"):
    resp = client.post("/api/v1/productions", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestAuth:
    def test_missing_token_is_rejected(self, client):
        resp = client.get("/api/v1/productions")
        assert resp.status_code == 401

    def test_wrong_token_is_rejected(self, client):
        resp = client.get("/api/v1/productions", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_correct_token_is_accepted(self, client, auth_headers):
        resp = client.get("/api/v1/productions", headers=auth_headers)
        assert resp.status_code == 200


class TestProductionCrud:
    def test_create_and_fetch_production(self, client, auth_headers):
        created = _create_production(client, auth_headers, name="Noční směna")
        resp = client.get(f"/api/v1/productions/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Noční směna"

    def test_fetch_unknown_production_is_404(self, client, auth_headers):
        resp = client.get(f"/api/v1/productions/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


class TestCallSheetCreation:
    def test_create_call_sheet_with_initial_revision_a(self, client, auth_headers):
        production = _create_production(client, auth_headers)
        payload = {
            "shoot_date": "2026-10-01",
            "day_number": 5,
            "day_count": 20,
            "unit_name": "Main Unit",
            "initial_revision": {
                "general_crew_call": "06:30",
                "schedule_items": [
                    {
                        "order_index": 1,
                        "scene_number": "10",
                        "int_ext": "INT",
                        "day_night": "DAY",
                        "set_description": "Kitchen",
                        "page_count_eighths": 8,
                    }
                ],
            },
        }
        resp = client.post(
            f"/api/v1/productions/{production['id']}/call-sheets",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["current_revision"]["revision_letter"] == "A"
        assert body["current_revision"]["is_current"] is True
        assert len(body["current_revision"]["schedule_items"]) == 1

    def test_create_call_sheet_for_unknown_production_is_404(self, client, auth_headers):
        resp = client.post(
            f"/api/v1/productions/{uuid.uuid4()}/call-sheets",
            json={
                "shoot_date": "2026-10-01",
                "day_number": 1,
                "day_count": 1,
                "initial_revision": {},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_public_endpoint_needs_no_auth(self, client, auth_headers):
        production = _create_production(client, auth_headers)
        create_resp = client.post(
            f"/api/v1/productions/{production['id']}/call-sheets",
            json={
                "shoot_date": "2026-10-01",
                "day_number": 1,
                "day_count": 1,
                "initial_revision": {"general_crew_call": "07:00"},
            },
            headers=auth_headers,
        )
        call_sheet_id = create_resp.json()["id"]

        public_resp = client.get(f"/api/v1/public/call-sheets/{call_sheet_id}")
        assert public_resp.status_code == 200
        assert public_resp.json()["current_revision"]["general_crew_call"] == "07:00"


class TestRevisionSupersession:
    def test_publishing_new_revision_supersedes_the_old_one(self, client, auth_headers):
        production = _create_production(client, auth_headers)
        create_resp = client.post(
            f"/api/v1/productions/{production['id']}/call-sheets",
            json={
                "shoot_date": "2026-10-01",
                "day_number": 1,
                "day_count": 1,
                "initial_revision": {"general_crew_call": "06:00"},
            },
            headers=auth_headers,
        )
        call_sheet_id = create_resp.json()["id"]
        assert create_resp.json()["current_revision"]["revision_letter"] == "A"

        revision_b = client.post(
            f"/api/v1/call-sheets/{call_sheet_id}/revisions",
            json={"general_crew_call": "05:30", "safety_notes": "Weather call-time push"},
            headers=auth_headers,
        )
        assert revision_b.status_code == 201
        assert revision_b.json()["revision_letter"] == "B"
        assert revision_b.json()["is_current"] is True

        refreshed = client.get(f"/api/v1/call-sheets/{call_sheet_id}", headers=auth_headers)
        current = refreshed.json()["current_revision"]
        assert current["revision_letter"] == "B"
        assert current["general_crew_call"] == "05:30"

    def test_only_one_revision_is_ever_current(self, db_session):
        """Service-layer test (bypassing HTTP) asserting the DB-level
        invariant directly: after N revisions, exactly one row has
        is_current=True."""
        from app.models.production import Production

        production = Production(name="Direct DB test")
        db_session.add(production)
        db_session.flush()

        call_sheet = create_call_sheet(
            db_session, production.id, _minimal_call_sheet_payload()
        )
        for _ in range(3):
            publish_revision(db_session, call_sheet, CallSheetRevisionCreate())

        db_session.refresh(call_sheet)
        current_flags = [r.is_current for r in call_sheet.revisions]
        assert current_flags.count(True) == 1
        assert len(call_sheet.revisions) == 4  # A + 3 more
        assert call_sheet.current_revision.revision_letter == "D"

    def test_current_revision_uniqueness_is_enforced_by_the_database(self, db_session):
        """FR-69: a partial unique index on call_sheet_revisions(call_sheet_id)
        WHERE is_current backs up publish_revision's application-layer
        invariant. Insert a second current revision directly, bypassing
        the service function entirely, and assert Postgres itself refuses
        it rather than silently allowing two "current" revisions."""
        from sqlalchemy.exc import IntegrityError

        from app.models.production import Production

        production = Production(name="DB-level uniqueness test")
        db_session.add(production)
        db_session.flush()

        call_sheet = create_call_sheet(
            db_session, production.id, _minimal_call_sheet_payload()
        )
        db_session.add(
            CallSheetRevision(
                call_sheet_id=call_sheet.id,
                revision_letter="B",
                is_current=True,
            )
        )
        with pytest.raises(IntegrityError, match=str(call_sheet.id)):
            db_session.flush()
        db_session.rollback()  # the failed flush leaves the session's transaction inactive

    def test_27th_revision_in_one_day_is_rejected(self, db_session):
        """Exercises the documented A-Z exhaustion guard rather than
        assuming it works — this is exactly the kind of edge case that's
        cheap to test and expensive to discover live on a shoot day."""
        from app.models.production import Production

        production = Production(name="Revision limit test")
        db_session.add(production)
        db_session.flush()

        call_sheet = create_call_sheet(
            db_session, production.id, _minimal_call_sheet_payload()
        )
        for _ in range(25):  # already have A (1) + 25 = 26 total
            publish_revision(db_session, call_sheet, CallSheetRevisionCreate())

        with pytest.raises(ValueError, match="already has 26 revisions") as refused:
            publish_revision(db_session, call_sheet, CallSheetRevisionCreate())
        assert str(call_sheet.id) not in str(refused.value)
        assert f"Day {call_sheet.day_number}" in str(refused.value)

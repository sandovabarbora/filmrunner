"""FR-96: the pilot's numbers per shoot day, read from the FR-36 read receipts."""

import uuid
from datetime import date, datetime

from fastapi.testclient import TestClient

from app.config import get_settings
from app.models.call_sheet import CallSheetRevision
from app.models.seen import RevisionView
from scripts import pilot_metrics

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _member(client: TestClient, pid: str, name: str, standard_call_time: str | None = None) -> dict:
    cid = client.post("/api/v1/contacts", json={"name": name, "phone": "777 000 111"}, headers=AUTH).json()["id"]
    body = {"contact_id": cid, "department": "Camera", "position": "x", "standard_call_time": standard_call_time}
    return client.post(f"/api/v1/productions/{pid}/crew-members", json=body, headers=AUTH).json()


def _seen(db_session, revision_id, member: dict, at: datetime) -> None:
    db_session.add(RevisionView(revision_id=revision_id, crew_member_id=uuid.UUID(member["id"]), first_seen_at=at, last_seen_at=at))
    db_session.flush()


def test_before_call_and_within_30_minutes(client: TestClient, db_session) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Pilot"}, headers=AUTH).json()["id"]
    tomas = _member(client, pid, "Tomáš Novák", standard_call_time="05:45")  # his own call beats the general 06:30
    eva = _member(client, pid, "Eva Malá")
    _member(client, pid, "Jana Bílá")  # never opens anything
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-23", "day_number": 1, "day_count": 3,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH).json()
    client.post(f"/api/v1/call-sheets/{sheet['id']}/revisions", json={"general_crew_call": "06:30", "schedule_items": []}, headers=AUTH)

    rev_b = db_session.query(CallSheetRevision).filter_by(call_sheet_id=uuid.UUID(sheet["id"]), revision_letter="B").one()
    rev_b.created_at = datetime(2026, 9, 22, 20, 0)  # published 22:00 Prague the night before (UTC+2)
    db_session.flush()
    _seen(db_session, rev_b.id, tomas, datetime(2026, 9, 22, 20, 10))  # 10 min after publish, long before 05:45
    _seen(db_session, rev_b.id, eva, datetime(2026, 9, 23, 4, 45))  # 06:45 Prague: after the 06:30 call, hours after publish

    (day,) = pilot_metrics.day_metrics(db_session, uuid.UUID(pid))
    assert (day.day_number, day.shoot_date, day.current_letter) == (1, date(2026, 9, 23), "B")
    assert (day.crew, day.with_call, day.opened_before_call) == (3, 3, 1)
    assert [(r.letter, r.opened_fast, r.crew) for r in day.later_revisions] == [("B", 1, 3)]

    text = pilot_metrics.report([day])
    assert "opened before own call: 1 / 3 (33 %)" in text and "REV B opened within 30 min: 1 / 3 (33 %)" in text


def test_personal_call_is_the_bar_not_the_general_call(client: TestClient, db_session) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Pilot"}, headers=AUTH).json()["id"]
    tomas = _member(client, pid, "Tomáš Novák", standard_call_time="05:45")
    sheet = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH).json()
    rev_a = db_session.query(CallSheetRevision).filter_by(call_sheet_id=uuid.UUID(sheet["id"])).one()
    _seen(db_session, rev_a.id, tomas, datetime(2026, 9, 23, 4, 0))  # 06:00 Prague: before 06:30, after his own 05:45

    (day,) = pilot_metrics.day_metrics(db_session, uuid.UUID(pid))
    assert day.opened_before_call == 0
    assert "later revisions: none (REV A only)" in pilot_metrics.report([day])


def test_no_crew_prints_no_data_not_zero(client: TestClient, db_session) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Empty"}, headers=AUTH).json()["id"]
    client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": "2026-09-23", "day_number": 1, "day_count": 1,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}, headers=AUTH)

    text = pilot_metrics.report(pilot_metrics.day_metrics(db_session, uuid.UUID(pid)))
    assert "no data" in text and "%" not in text


def test_call_at_is_prague_wall_clock_in_utc() -> None:
    assert pilot_metrics.call_at(date(2026, 9, 23), "06:30") == datetime(2026, 9, 23, 4, 30)  # CEST
    assert pilot_metrics.call_at(date(2026, 12, 1), "06:30") == datetime(2026, 12, 1, 5, 30)  # CET
    assert pilot_metrics.call_at(date(2026, 9, 23), None) is None
    assert pilot_metrics.call_at(date(2026, 9, 23), "tbd") is None

"""FR-219: a publish made from an older revision must not overwrite the newer one."""

from fastapi.testclient import TestClient

from .test_replan import AUTH, _day, _production


def _publish(client: TestClient, sheet_id: str, **body):
    return client.post(f"/api/v1/call-sheets/{sheet_id}/revisions", json=body, headers=AUTH)


def _new_day(client: TestClient) -> dict:
    return _day(client, _production(client), 1, "2026-11-20", [])


def test_publish_from_an_older_revision_is_refused_and_the_newer_one_stands(client: TestClient) -> None:
    sheet = _new_day(client)
    assert _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_letter="A").status_code == 201

    stale = _publish(client, sheet["id"], general_crew_call="06:30", safety_notes="Mine", expected_revision_letter="A")

    assert stale.status_code == 409
    assert "REV B" in stale.json()["detail"]
    current = client.get(f"/api/v1/call-sheets/{sheet['id']}", headers=AUTH).json()["current_revision"]
    assert current["revision_letter"] == "B" and current["general_crew_call"] == "04:44"


def test_retry_of_a_publish_whose_response_was_lost_returns_the_same_revision(client: TestClient) -> None:
    sheet = _new_day(client)
    first = _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_letter="A")
    retry = _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_letter="A")
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]


def test_publish_without_the_field_still_works_for_old_clients(client: TestClient) -> None:
    sheet = _new_day(client)
    assert _publish(client, sheet["id"], general_crew_call="04:44").status_code == 201
    assert _publish(client, sheet["id"], general_crew_call="05:00").json()["revision_letter"] == "C"

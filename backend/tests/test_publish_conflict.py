"""FR-219: a publish made from an older revision must not overwrite the newer one."""

from fastapi.testclient import TestClient

from .test_replan import AUTH, _day, _production


def _publish(client: TestClient, sheet_id: str, **body):
    return client.post(f"/api/v1/call-sheets/{sheet_id}/revisions", json=body, headers=AUTH)


def _new_day(client: TestClient) -> dict:
    return _day(client, _production(client), 1, "2026-11-20", [])


def test_publish_from_an_older_revision_is_refused_and_the_newer_one_stands(client: TestClient) -> None:
    sheet = _new_day(client)
    base = sheet["current_revision"]["id"]
    assert _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_id=base).status_code == 201

    stale = _publish(client, sheet["id"], general_crew_call="06:30", safety_notes="Mine", expected_revision_id=base)

    assert stale.status_code == 412
    assert "REV B" in stale.json()["detail"]
    current = client.get(f"/api/v1/call-sheets/{sheet['id']}", headers=AUTH).json()["current_revision"]
    assert current["revision_letter"] == "B" and current["general_crew_call"] == "04:44"


def test_retry_of_a_publish_whose_response_was_lost_returns_the_same_revision(client: TestClient) -> None:
    sheet = _new_day(client)
    base = sheet["current_revision"]["id"]
    first = _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_id=base)
    retry = _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_id=base)
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]


def test_publish_without_the_field_still_works_for_old_clients(client: TestClient) -> None:
    sheet = _new_day(client)
    assert _publish(client, sheet["id"], general_crew_call="04:44").status_code == 201
    assert _publish(client, sheet["id"], general_crew_call="05:00").json()["revision_letter"] == "C"


def test_a_planned_day_published_by_someone_else_is_not_published_over(client: TestClient) -> None:
    """Its REV A is replaced by a new REV A, so the letter alone cannot show the day moved on."""
    sheet = _day(client, _production(client), 1, "2026-11-20", [], draft=True)
    base = sheet["current_revision"]["id"]
    won = _publish(client, sheet["id"], general_crew_call="04:44", expected_revision_id=base)
    assert won.status_code == 201 and won.json()["revision_letter"] == "A"

    stale = _publish(client, sheet["id"], general_crew_call="06:30", expected_revision_id=base)

    assert stale.status_code == 412
    assert client.get(f"/api/v1/call-sheets/{sheet['id']}", headers=AUTH).json()["current_revision"]["general_crew_call"] == "04:44"


def test_clearing_a_field_someone_else_filled_is_a_different_edit_not_a_retry(client: TestClient) -> None:
    sheet = _new_day(client)
    base = sheet["current_revision"]["id"]
    first = _publish(client, sheet["id"], general_crew_call="07:00", weather_forecast="Rain", expected_revision_id=base).json()
    second = _publish(client, sheet["id"], general_crew_call="07:00", weather_forecast="Rain", expected_revision_id=first["id"], safety_notes="x")
    assert second.status_code == 201

    cleared = _publish(client, sheet["id"], general_crew_call="07:00", safety_notes="x", expected_revision_id=first["id"])

    assert cleared.status_code == 412

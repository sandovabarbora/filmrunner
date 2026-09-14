"""FR-14: production contacts on the public call sheet.

Head of day, heads of department (tap-to-call on the phone), and the
nearest hospital from the day's first location.
"""

from fastapi.testclient import TestClient

AUTH = {"Authorization": "Bearer dev-only-token-change-me"}


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Contacts test"}, headers=AUTH).json()["id"]


def _contact(client: TestClient, name: str, phone: str | None) -> str:
    return client.post("/api/v1/contacts", json={"name": name, "phone": phone}, headers=AUTH).json()["id"]


def _crew(client: TestClient, production_id: str, contact_id: str, department: str, position: str, hod: bool) -> str:
    resp = client.post(
        f"/api/v1/productions/{production_id}/crew-members",
        json={"contact_id": contact_id, "department": department, "position": position, "is_head_of_department": hod},
        headers=AUTH,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_public_sheet_lists_head_of_day_department_heads_and_hospital(client: TestClient) -> None:
    pid = _production(client)
    ad = _crew(client, pid, _contact(client, "Eva Dvořáková", "+420 777 111 222"), "AD", "1st AD", hod=True)
    _crew(client, pid, _contact(client, "Tomáš Novák", "+420 601 234 567"), "Electric", "Gaffer", hod=True)
    _crew(client, pid, _contact(client, "Petr Malý", "+420 602 000 000"), "Electric", "Best boy", hod=False)
    loc = client.post(
        f"/api/v1/productions/{pid}/locations",
        json={"name": "Riverbank, Troja", "nearest_hospital": "FN Bulovka, Budínova 2, Praha 8"},
        headers=AUTH,
    ).json()["id"]
    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={
            "shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "unit_name": "Main Unit",
            "initial_revision": {
                "general_crew_call": "06:30", "head_of_day_crew_member_id": ad,
                "schedule_items": [{"order_index": 1, "scene_number": "42", "int_ext": "EXT", "day_night": "DAY",
                                    "set_description": "Riverbank", "page_count_eighths": 8, "location_id": loc}],
            },
        },
        headers=AUTH,
    )
    assert sheet.status_code == 201, sheet.text
    public = client.get(f"/api/v1/public/call-sheets/{sheet.json()['id']}").json()
    contacts = public["contacts"]
    assert contacts["head_of_day"]["name"] == "Eva Dvořáková"
    assert contacts["head_of_day"]["phone"] == "+420 777 111 222"
    heads = [(c["department"], c["name"]) for c in contacts["department_heads"]]
    assert heads == [("AD", "Eva Dvořáková"), ("Electric", "Tomáš Novák")]  # sorted by department, best boy excluded
    assert contacts["nearest_hospital"] == "FN Bulovka, Budínova 2, Praha 8"


def test_head_of_department_without_phone_is_listed_with_null_phone(client: TestClient) -> None:
    """Failure case: no number on file must not drop the person from the list."""
    pid = _production(client)
    _crew(client, pid, _contact(client, "Jana Bez Čísla", None), "Costume", "Costume designer", hod=True)
    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"schedule_items": []}},
        headers=AUTH,
    ).json()
    contacts = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["contacts"]
    assert contacts["head_of_day"] is None
    assert contacts["department_heads"] == [
        {"name": "Jana Bez Čísla", "department": "Costume", "position": "Costume designer", "phone": None, "email": None}
    ]
    assert contacts["nearest_hospital"] is None


def test_head_of_day_must_belong_to_the_production(client: TestClient) -> None:
    pid_a = _production(client)
    pid_b = _production(client)
    foreign = _crew(client, pid_b, _contact(client, "Cizí", None), "AD", "1st AD", hod=True)
    resp = client.post(
        f"/api/v1/productions/{pid_a}/call-sheets",
        json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1,
              "initial_revision": {"head_of_day_crew_member_id": foreign, "schedule_items": []}},
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert "head of day" in resp.json()["detail"].lower()

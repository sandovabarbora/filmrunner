from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.config import get_settings
from app.services.dashboard import build_dashboard

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _in(days: int) -> str:
    return (datetime.now(ZoneInfo("Europe/Prague")).date() + timedelta(days=days)).isoformat()


def _production(client: TestClient, name: str, people: int = 2) -> tuple[str, list[dict]]:
    pid = client.post("/api/v1/productions", json={"name": name}, headers=AUTH).json()["id"]
    crew = []
    for i in range(people):
        cid = client.post("/api/v1/contacts", json={"name": f"{name} {i}", "phone": f"77700011{i}"}, headers=AUTH).json()["id"]
        crew.append(client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Light", "position": "x"}, headers=AUTH).json())
    return pid, crew


def _day(client: TestClient, pid: str, days: int, number: int = 1) -> dict:
    return client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": _in(days), "day_number": number, "day_count": 9, "unit_name": "Main",
        "initial_revision": {"general_crew_call": "07:00", "schedule_items": []},
    }, headers=AUTH).json()


def _revise(client: TestClient, sheet_id: str) -> None:
    assert client.post(f"/api/v1/call-sheets/{sheet_id}/revisions", json={"general_crew_call": "06:00", "schedule_items": []}, headers=AUTH).status_code == 201


def _dashboard(client: TestClient, headers: dict = AUTH) -> dict:
    response = client.get("/api/v1/me/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_people_who_do_not_know_about_a_change_lead_with_the_count(client: TestClient) -> None:
    pid, crew = _production(client, "Voda")
    sheet = _day(client, pid, 1)
    _revise(client, sheet["id"])
    token = crew[0]["personal_token"]
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/confirm/{token}", json={"revision_letter": "B"}).status_code == 200

    item = next(i for i in _dashboard(client)["items"] if i["production_id"] == pid)
    assert (item["kind"], item["revision_letter"], item["total"], item["confirmed"], item["not_opened"]) == ("unconfirmed", "B", 2, 1, 1)
    assert item["call_sheet_id"] == sheet["id"] and item["crew_call"] == "06:00"


def test_a_day_not_yet_published_counts_while_it_is_close(client: TestClient) -> None:
    pid, _ = _production(client, "Koncept")
    near = client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": _in(1), "day_number": 1, "day_count": 9, "unit_name": "Main", "draft": True,
        "initial_revision": {"general_crew_call": "07:00", "schedule_items": []},
    }, headers=AUTH).json()
    client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": _in(9), "day_number": 2, "day_count": 9, "unit_name": "Main", "draft": True,
        "initial_revision": {"general_crew_call": "07:00", "schedule_items": []},
    }, headers=AUTH)
    assert [(i["kind"], i["call_sheet_id"]) for i in _dashboard(client)["items"] if i["production_id"] == pid] == [("unpublished", near["id"])]


def test_a_fully_confirmed_day_is_on_track(client: TestClient) -> None:
    pid, crew = _production(client, "Klid", people=1)
    sheet = _day(client, pid, 0)
    assert client.post(f"/api/v1/public/call-sheets/{sheet['id']}/confirm/{crew[0]['personal_token']}", json={"revision_letter": "A"}).status_code == 200

    board = _dashboard(client)
    assert not [i for i in board["items"] if i["production_id"] == pid]
    row = next(p for p in board["on_track"] if p["production_id"] == pid)
    assert row["next_call_sheet_id"] == sheet["id"] and row["crew_call"] == "07:00"


def test_a_first_revision_two_days_out_is_not_a_problem_yet(client: TestClient) -> None:
    pid, _ = _production(client, "Brzy")
    _day(client, pid, 2)
    assert not [i for i in _dashboard(client)["items"] if i["production_id"] == pid]


def test_a_changed_day_two_days_out_is_already_a_problem(client: TestClient) -> None:
    pid, _ = _production(client, "Zmena")
    sheet = _day(client, pid, 2)
    _revise(client, sheet["id"])
    assert [i["kind"] for i in _dashboard(client)["items"] if i["production_id"] == pid] == ["unconfirmed"]


def test_days_past_the_watch_window_and_past_days_raise_nothing(client: TestClient) -> None:
    pid, _ = _production(client, "Daleko")
    far = _day(client, pid, 12, number=2)
    _revise(client, far["id"])
    _day(client, pid, -3, number=1)
    board = _dashboard(client)
    assert not [i for i in board["items"] if i["production_id"] == pid]
    assert next(p for p in board["on_track"] if p["production_id"] == pid)["next_call_sheet_id"] == far["id"]


def test_a_cancelled_day_is_not_chased(client: TestClient) -> None:
    pid, _ = _production(client, "Zruseno")
    sheet = _day(client, pid, 1)
    assert client.post(f"/api/v1/call-sheets/{sheet['id']}/cancel", headers=AUTH).status_code in (200, 201)
    assert not [i for i in _dashboard(client)["items"] if i["production_id"] == pid]


def test_soonest_comes_first_across_productions(client: TestClient) -> None:
    later, _ = _production(client, "Pozdeji")
    _revise(client, _day(client, later, 2)["id"])
    sooner, _ = _production(client, "Driv")
    _day(client, sooner, 0)
    ours = [i["production_id"] for i in _dashboard(client)["items"] if i["production_id"] in (later, sooner)]
    assert ours == [sooner, later]


def test_a_member_sees_only_their_own_productions_and_no_personal_data(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    key = ec.generate_private_key(ec.SECP256R1())

    class _Signing:
        def get_signing_key_from_jwt(self, token: str):
            return type("K", (), {"key": key.public_key()})()

    monkeypatch.setattr(auth, "_jwk_client", lambda: _Signing())

    def member(email: str) -> dict:
        now = int(datetime.now().timestamp())
        token = jwt.encode({"sub": f"uid-{email}", "email": email, "aud": "authenticated", "iat": now, "exp": now + 600}, key, algorithm="ES256")
        return {"Authorization": f"Bearer {token}"}

    mine, _ = _production(client, "Moje")
    other, _ = _production(client, "Cizi")
    _day(client, mine, 0)
    _day(client, other, 0)
    assert client.post(f"/api/v1/productions/{mine}/members", json={"email": "ad@example.com", "role": "viewer"}, headers=AUTH).status_code in (200, 201)

    response = client.get("/api/v1/me/dashboard", headers=member("ad@example.com"))
    assert response.status_code == 200, response.text
    board = response.json()
    assert [i["production_id"] for i in board["items"]] == [mine]
    assert "token" not in response.text and "phone" not in response.text


def test_nobody_with_no_productions_gets_an_empty_board() -> None:
    assert build_dashboard(None, [], date.today()).model_dump() == {"items": [], "on_track": []}


def test_the_dashboard_needs_a_sign_in(client: TestClient) -> None:
    assert client.get("/api/v1/me/dashboard").status_code in (401, 403)


def test_a_published_day_with_nobody_on_it_needs_attention_rather_than_being_on_track(client: TestClient) -> None:
    """FR-222: "everyone has confirmed" was true of an empty list."""
    pid, _ = _production(client, "Prázdno", people=0)
    sheet = _day(client, pid, 2)
    board = _dashboard(client)
    item = next(i for i in board["items"] if i["production_id"] == pid)
    assert (item["kind"], item["call_sheet_id"], item["revision_letter"], item["total"]) == ("no_crew", sheet["id"], "A", 0)
    assert pid not in [p["production_id"] for p in board["on_track"]]


def test_an_empty_day_past_the_watch_window_waits(client: TestClient) -> None:
    pid, _ = _production(client, "Daleko", people=0)
    _day(client, pid, 5)
    board = _dashboard(client)
    assert pid not in [i["production_id"] for i in board["items"]] and pid in [p["production_id"] for p in board["on_track"]]


def test_a_day_with_only_cast_called_is_not_empty(client: TestClient) -> None:
    pid, _ = _production(client, "Herci", people=0)
    contact = client.post("/api/v1/contacts", json={"name": "Anna"}, headers=AUTH).json()["id"]
    actor = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact, "character_name": "Hero"}, headers=AUTH).json()
    client.post(f"/api/v1/productions/{pid}/call-sheets", json={"shoot_date": _in(1), "day_number": 1, "day_count": 1, "initial_revision": {
        "general_crew_call": "07:00", "cast_calls": [{"cast_member_id": actor["id"], "status_code": "W"}]}}, headers=AUTH)
    item = next(i for i in _dashboard(client)["items"] if i["production_id"] == pid)
    assert item["kind"] == "unconfirmed"


def test_on_the_same_day_people_who_do_not_know_lead_then_an_empty_day_then_an_unpublished_one(client: TestClient) -> None:
    waiting, _ = _production(client, "C čeká")
    sheet = _day(client, waiting, 1)
    _revise(client, sheet["id"])
    empty, _ = _production(client, "A prázdno", people=0)
    _day(client, empty, 1)
    planned, _ = _production(client, "B plán")
    client.post(f"/api/v1/productions/{planned}/call-sheets", json={"shoot_date": _in(1), "day_number": 1, "day_count": 1, "draft": True, "initial_revision": {}}, headers=AUTH)
    kinds = [i["kind"] for i in _dashboard(client)["items"] if i["production_id"] in (waiting, empty, planned)]
    assert kinds == ["unconfirmed", "no_crew", "unpublished"]

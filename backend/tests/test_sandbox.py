from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app import config
from app.config import get_settings
from app.models.production import Contact, Production
from app.routers import productions as productions_router
from app.routers import sandbox as sandbox_router
from app.services.sandbox import purge_expired

SERVICE = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


@pytest.fixture(autouse=True)
def _fresh_rate_window():
    sandbox_router._per_ip.reset()


def _start(client: TestClient) -> dict:
    response = client.post("/api/v1/public/sandbox/sessions")
    assert response.status_code == 201, response.text
    return {p["key"]: p for p in response.json()["personas"]}


def _as(persona: dict) -> dict:
    return {"Authorization": f"Bearer {persona['token']}"}


def _real_film(client: TestClient) -> tuple[str, str]:
    pid = client.post("/api/v1/productions", json={"name": "Skutečný film"}, headers=SERVICE).json()["id"]
    contact = client.post("/api/v1/contacts", json={"name": "Skutečná Osoba", "phone": "+420777000999"}, headers=SERVICE).json()["id"]
    assert client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "Zvuk", "position": "x"}, headers=SERVICE).status_code == 201
    return pid, contact


def test_each_persona_opens_on_its_own_view_of_the_world(client: TestClient) -> None:
    personas = _start(client)
    films = lambda key: sorted(p["name"] for p in client.get("/api/v1/productions", headers=_as(personas[key])).json())
    assert films("produkcni") == ["Kanál", "Nádraží", "Poslední léto", "Tichá voda"]
    assert films("ad") == ["Tichá voda"]
    assert films("producent") == ["Poslední léto", "Tichá voda"]

    board = client.get("/api/v1/me/dashboard", headers=_as(personas["produkcni"])).json()
    assert {i["kind"] for i in board["items"]} == {"unconfirmed", "unpublished"}
    assert sorted(p["production_name"] for p in board["on_track"]) == ["Nádraží", "Poslední léto"]


def test_a_read_only_persona_cannot_publish_and_an_ad_can(client: TestClient) -> None:
    personas = _start(client)
    board = client.get("/api/v1/me/dashboard", headers=_as(personas["ad"])).json()
    sheet = board["items"][0]["call_sheet_id"]
    payload = {"general_crew_call": "06:00", "schedule_items": []}
    assert client.post(f"/api/v1/call-sheets/{sheet}/revisions", json=payload, headers=_as(personas["producent"])).status_code == 403
    assert client.post(f"/api/v1/call-sheets/{sheet}/revisions", json=payload, headers=_as(personas["ad"])).status_code == 201


def test_a_link_persona_works_like_a_real_crew_link(client: TestClient) -> None:
    gaffer = _start(client)["gaffer"]
    mine = client.get(f"/api/v1/public/call-sheets/{gaffer['call_sheet_id']}/me/{gaffer['personal_token']}").json()
    assert mine["name"] == "Tomáš Novák" and mine["personal_call"] == "05:00" and mine["call_before"] == "07:00"


def test_a_persona_cannot_reach_real_data(client: TestClient) -> None:
    pid, contact = _real_film(client)
    owner = _as(_start(client)["produkcni"])
    assert "Skutečný film" not in client.get("/api/v1/productions", headers=owner).text
    assert client.get(f"/api/v1/productions/{pid}", headers=owner).status_code == 403
    assert client.get(f"/api/v1/productions/{pid}/call-sheets", headers=owner).status_code == 403
    assert client.get("/api/v1/contacts?q=Skute", headers=owner).json() == []
    assert client.patch(f"/api/v1/contacts/{contact}", json={"phone": "666"}, headers=owner).status_code == 403
    assert "Skutečný film" not in client.get("/api/v1/me/dashboard", headers=owner).text


def test_worlds_do_not_see_each_other(client: TestClient) -> None:
    first, second = _start(client), _start(client)
    theirs = client.get("/api/v1/productions", headers=_as(first["produkcni"])).json()[0]["id"]
    assert client.get(f"/api/v1/productions/{theirs}", headers=_as(second["produkcni"])).status_code == 403


def test_the_real_side_never_lists_a_test_film(client: TestClient) -> None:
    _start(client)
    assert "Tichá voda" not in client.get("/api/v1/productions", headers=SERVICE).text
    assert "Tichá voda" not in client.get("/api/v1/me/dashboard", headers=SERVICE).text


def test_members_cannot_cross_in_either_direction(client: TestClient) -> None:
    pid, _ = _real_film(client)
    owner = _as(_start(client)["produkcni"])
    film = client.post("/api/v1/productions", json={"name": "Vlastní zkouška"}, headers=owner).json()["id"]
    assert client.post(f"/api/v1/productions/{film}/members", json={"email": "real@example.com", "role": "viewer"}, headers=owner).status_code == 403
    assert client.post(f"/api/v1/productions/{pid}/members", json={"email": "produkcni.abc@sandbox.invalid", "role": "owner"}, headers=SERVICE).status_code == 403


def test_a_film_a_persona_creates_stays_in_the_test_world(client: TestClient, db_session) -> None:
    owner = _as(_start(client)["produkcni"])
    film = client.post("/api/v1/productions", json={"name": "Vlastní zkouška"}, headers=owner).json()["id"]
    assert db_session.get(Production, film).sandbox_session is not None
    assert "Vlastní zkouška" not in client.get("/api/v1/productions", headers=SERVICE).text


@pytest.mark.parametrize("key", ["wrong-key", ""])
def test_a_forged_token_is_refused(client: TestClient, key: str) -> None:
    claims = {"iss": "filmrunner-sandbox", "sub": "sandbox-x-y", "email": "produkcni.x@sandbox.invalid", "exp": 9999999999}
    forged = jwt.encode(claims, key or "x" * 32, algorithm="HS256")
    assert client.get("/api/v1/productions", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_a_token_signed_with_the_service_token_itself_is_refused(client: TestClient) -> None:
    claims = {"iss": "filmrunner-sandbox", "sub": "sandbox-x-y", "email": "x.y@sandbox.invalid", "exp": 9999999999}
    forged = jwt.encode(claims, get_settings().api_bearer_token, algorithm="HS256")
    assert client.get("/api/v1/productions", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_an_expired_token_is_refused(client: TestClient) -> None:
    from app.sandbox_tokens import issue_token
    token = issue_token("abc", "ad", datetime.now(timezone.utc) - timedelta(hours=1))
    assert client.get("/api/v1/productions", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_it_can_be_switched_off_with_one_setting(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _as(_start(client)["produkcni"])
    monkeypatch.setattr(get_settings(), "sandbox_enabled", False, raising=False)
    assert client.post("/api/v1/public/sandbox/sessions").status_code == 404
    assert client.get("/api/v1/productions", headers=owner).status_code == 401
    assert config  # the setting lives in app.config


def test_starting_sessions_is_rate_limited(client: TestClient) -> None:
    for _ in range(5):
        assert client.post("/api/v1/public/sandbox/sessions").status_code == 201
    limited = client.post("/api/v1/public/sandbox/sessions")
    assert limited.status_code == 429 and limited.headers["Retry-After"]


def test_the_number_of_live_worlds_is_capped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sandbox_router, "MAX_LIVE_SESSIONS", 0)
    assert client.post("/api/v1/public/sandbox/sessions").status_code == 503


def test_an_old_world_is_deleted_whole_and_real_data_stays(client: TestClient, db_session) -> None:
    pid, contact = _real_film(client)
    _start(client)
    worlds = db_session.query(Production).filter(Production.sandbox_session.is_not(None)).all()
    assert worlds
    for world in worlds:
        world.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25)
    db_session.commit()

    purge_expired(db_session)
    db_session.commit()

    assert db_session.query(Production).filter(Production.sandbox_session.is_not(None)).count() == 0
    assert db_session.query(Contact).filter(Contact.name == "Tomáš Novák").count() == 0
    assert db_session.get(Production, pid) is not None and db_session.get(Contact, contact) is not None


@pytest.mark.parametrize("kind,body", [("crew-members", {"department": "x", "position": "x"}), ("cast-members", {"character_name": "X"})])
def test_a_persona_cannot_pull_a_real_contact_in_by_id(client: TestClient, kind: str, body: dict) -> None:
    """A contact's id leaks through the photo URL on any sheet, so the id alone must not be enough."""
    _, contact = _real_film(client)
    owner = _as(_start(client)["produkcni"])
    film = client.post("/api/v1/productions", json={"name": "Past"}, headers=owner).json()["id"]
    response = client.post(f"/api/v1/productions/{film}/{kind}", json={"contact_id": contact, **body}, headers=owner)
    assert response.status_code == 404
    assert "777000999" not in response.text


def test_a_test_contact_cannot_join_a_real_film(client: TestClient) -> None:
    pid, _ = _real_film(client)
    owner = _as(_start(client)["produkcni"])
    contact = client.post("/api/v1/contacts", json={"name": "Testovací"}, headers=owner).json()["id"]
    response = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "x", "position": "x"}, headers=SERVICE)
    assert response.status_code == 404


def test_purging_goes_by_ownership_and_takes_what_a_persona_added(client: TestClient, db_session) -> None:
    pid, real = _real_film(client)
    # Unused and real: it looks exactly like an orphan, and must survive.
    lonely = client.post("/api/v1/contacts", json={"name": "Osamělý Skutečný"}, headers=SERVICE).json()["id"]
    owner = _as(_start(client)["produkcni"])
    added = client.post("/api/v1/contacts", json={"name": "Přidaný Testem"}, headers=owner).json()["id"]
    client.post("/api/v1/productions", json={"name": "Nový test"}, headers=owner)
    for world in db_session.query(Production).filter(Production.sandbox_session.is_not(None), Production.name == "Tichá voda"):
        world.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25)
    db_session.commit()

    purge_expired(db_session)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(Contact, added) is None
    assert db_session.query(Production).filter(Production.name == "Nový test").count() == 0
    assert db_session.get(Contact, real) is not None and db_session.get(Contact, lonely) is not None and db_session.get(Production, pid) is not None


def test_a_world_cannot_grow_without_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _as(_start(client)["produkcni"])
    monkeypatch.setattr(productions_router, "MAX_CONTACTS_PER_SESSION", 0)
    monkeypatch.setattr(productions_router, "MAX_PRODUCTIONS_PER_SESSION", 0)
    assert client.post("/api/v1/contacts", json={"name": "Moc"}, headers=owner).status_code == 429
    assert client.post("/api/v1/productions", json={"name": "Moc"}, headers=owner).status_code == 429


def test_costly_features_are_closed_to_personas(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("a test world called an outside service")

    monkeypatch.setattr(productions_router.geocoding, "geocode", must_not_be_called)
    monkeypatch.setattr(productions_router.weather, "weather_suggestion", must_not_be_called)
    monkeypatch.setattr(productions_router.hospitals, "nearest_hospital_suggestion", must_not_be_called)
    monkeypatch.setattr(productions_router.call_sheet_pdf, "extract_contacts", must_not_be_called)
    owner = _as(_start(client)["produkcni"])
    film = client.post("/api/v1/productions", json={"name": "Drahé"}, headers=owner).json()["id"]
    pdf = {"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}
    assert client.post(f"/api/v1/productions/{film}/import/call-sheet-pdf", files=pdf, headers=owner).status_code == 403
    place = client.post(f"/api/v1/productions/{film}/locations", json={"name": "Tady", "address": "Někde 1", "geo_lat": 50.0, "geo_lng": 14.0}, headers=owner).json()
    assert client.get(f"/api/v1/productions/{film}/locations/{place['id']}/weather-suggestion?shoot_date=2031-01-01", headers=owner).json()["suggestion"] is None
    contact = client.post("/api/v1/contacts", json={"name": "Foto"}, headers=owner).json()["id"]
    client.post(f"/api/v1/productions/{film}/crew-members", json={"contact_id": contact, "department": "x", "position": "x"}, headers=owner)
    photo = {"file": ("x.png", b"x", "image/png")}
    assert client.post(f"/api/v1/contacts/{contact}/photo", files=photo, headers=owner).status_code == 403


def test_a_scene_cannot_borrow_a_location_from_another_film(client: TestClient) -> None:
    """The public sheet prints a scene's location, so this was a way to read any location by id, real ones included."""
    pid, _ = _real_film(client)
    real = client.post(f"/api/v1/productions/{pid}/locations", json={"name": "Skutečné místo"}, headers=SERVICE).json()["id"]
    personas = _start(client)
    board = client.get("/api/v1/me/dashboard", headers=_as(personas["ad"])).json()
    payload = {"general_crew_call": "06:00", "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "INT", "day_night": "DAY", "set_description": "x", "location_id": real, "page_count_eighths": 8}]}
    response = client.post(f"/api/v1/call-sheets/{board['items'][0]['call_sheet_id']}/revisions", json=payload, headers=_as(personas["ad"]))
    assert response.status_code == 422


def test_a_test_world_never_sends_push(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import notifications

    def must_not_be_called(**kwargs):
        raise AssertionError("the server called an endpoint an anonymous visitor supplied")

    monkeypatch.setattr(notifications, "is_configured", lambda: True)
    monkeypatch.setattr(notifications, "send", must_not_be_called)
    personas = _start(client)
    gaffer = personas["gaffer"]
    subscribe = client.post(f"/api/v1/public/crew/{gaffer['personal_token']}/push-subscription", json={"endpoint": "http://internal.test/", "keys": {"p256dh": "x", "auth": "y"}, "link_url": "x"})
    assert subscribe.status_code in (200, 201, 204, 422)
    response = client.post(f"/api/v1/call-sheets/{gaffer['call_sheet_id']}/revisions", json={"general_crew_call": "04:00", "schedule_items": []}, headers=_as(personas["ad"]))
    assert response.status_code == 201


def test_a_failing_purge_does_not_lock_everyone_out(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(db) -> None:
        raise SQLAlchemyError("stuck")

    monkeypatch.setattr(sandbox_router, "purge_expired", boom)
    assert client.post("/api/v1/public/sandbox/sessions").status_code == 201

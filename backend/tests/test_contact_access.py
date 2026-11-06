"""FR-220: contact rows are shared across productions, so attaching one and editing one are both access decisions."""

import io
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import Principal, require_principal
from app.config import get_settings
from app.main import app

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
ATTACKER = Principal(kind="user", subject="user-attacker", email="attacker@example.com")
AD = Principal(kind="user", subject="user-ad", email="ad@example.com")


@contextmanager
def signed_in_as(principal: Principal) -> Iterator[None]:
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_principal, None)


def _production(client: TestClient, name: str = "Film") -> str:
    return client.post("/api/v1/productions", json={"name": name}, headers=AUTH).json()["id"]


def _contact(client: TestClient, name: str = "Jana Novotná") -> str:
    return client.post("/api/v1/contacts", json={"name": name, "phone": "+420 777 000 111", "email": "jana@example.com"}, headers=AUTH).json()["id"]


def _on_crew(client: TestClient, pid: str, contact_id: str) -> None:
    resp = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact_id, "department": "Grip", "position": "Key grip"}, headers=AUTH)
    assert resp.status_code == 201, resp.text


def _on_cast(client: TestClient, pid: str, contact_id: str) -> None:
    resp = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact_id, "character_name": "Hana"}, headers=AUTH)
    assert resp.status_code == 201, resp.text


def _member(client: TestClient, pid: str, who: Principal, role: str) -> None:
    resp = client.post(f"/api/v1/productions/{pid}/members", json={"email": who.email, "role": role}, headers=AUTH)
    assert resp.status_code == 201, resp.text


def _attach_crew(client: TestClient, pid: str, contact_id: str):
    return client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact_id, "department": "Grip", "position": "Key grip"})


def _attach_cast(client: TestClient, pid: str, contact_id: str):
    return client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact_id, "character_name": "Hana"})


def _phone_of(client: TestClient, pid: str, contact_id: str) -> str:
    crew = client.get(f"/api/v1/productions/{pid}/crew-members", headers=AUTH).json()
    return next(m["contact"]["phone"] for m in crew if m["contact_id"] == contact_id)


class TestAttach:
    def test_a_stranger_cannot_pull_in_someone_elses_contact_as_crew(self, client: TestClient) -> None:
        victim_film, victim = _production(client), _contact(client)
        _on_crew(client, victim_film, victim)
        mine = _production(client, "Mine")
        _member(client, mine, ATTACKER, "owner")
        with signed_in_as(ATTACKER):
            resp = _attach_crew(client, mine, victim)
        assert resp.status_code == 404, resp.text
        assert "777" not in resp.text and "jana@example.com" not in resp.text

    def test_a_stranger_cannot_pull_in_someone_elses_cast_contact_as_cast(self, client: TestClient) -> None:
        victim_film, victim = _production(client), _contact(client)
        _on_cast(client, victim_film, victim)
        mine = _production(client, "Mine")
        _member(client, mine, ATTACKER, "owner")
        with signed_in_as(ATTACKER):
            resp = _attach_cast(client, mine, victim)
        assert resp.status_code == 404, resp.text

    def test_a_refused_contact_looks_the_same_as_one_that_does_not_exist(self, client: TestClient) -> None:
        """Failure case: the refusal must not confirm that an id belongs to someone."""
        victim_film, victim = _production(client), _contact(client)
        _on_crew(client, victim_film, victim)
        mine = _production(client, "Mine")
        _member(client, mine, ATTACKER, "owner")
        with signed_in_as(ATTACKER):
            refused = _attach_crew(client, mine, victim)
            unknown = _attach_crew(client, mine, "00000000-0000-4000-8000-000000000000")
        assert (refused.status_code, refused.json()) == (unknown.status_code, unknown.json())

    def test_a_contact_on_a_film_the_caller_can_see_can_be_reused(self, client: TestClient) -> None:
        last_film, person = _production(client, "Last film"), _contact(client)
        _on_crew(client, last_film, person)
        next_film = _production(client, "Next film")
        _member(client, last_film, AD, "viewer")
        _member(client, next_film, AD, "editor")
        with signed_in_as(AD):
            assert _attach_crew(client, next_film, person).status_code == 201

    def test_a_contact_nobody_uses_yet_can_be_attached_the_create_then_attach_flow(self, client: TestClient) -> None:
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            created = client.post("/api/v1/contacts", json={"name": "New Person", "phone": "602 000 111"})
            assert created.status_code == 201
            assert _attach_crew(client, mine, created.json()["id"]).status_code == 201
            second = client.post("/api/v1/contacts", json={"name": "New Actor"}).json()["id"]
            assert _attach_cast(client, mine, second).status_code == 201

    def test_the_service_token_stays_unrestricted(self, client: TestClient) -> None:
        film_a, film_b, person = _production(client), _production(client), _contact(client)
        _on_crew(client, film_a, person)
        _on_cast(client, film_b, person)


class TestEdit:
    def _shared(self, client: TestClient, *, other_role: str | None) -> tuple[str, str, str]:
        """A contact on the AD's film and on another one, where the AD holds `other_role` (None: not a member)."""
        mine, other, person = _production(client, "Mine"), _production(client, "Other"), _contact(client)
        _on_crew(client, mine, person)
        _on_crew(client, other, person)
        _member(client, mine, AD, "editor")
        if other_role:
            _member(client, other, AD, other_role)
        return mine, other, person

    def test_a_contact_also_on_a_stranger_film_cannot_be_rewritten(self, client: TestClient) -> None:
        mine, _other, person = self._shared(client, other_role=None)
        with signed_in_as(AD):
            resp = client.patch(f"/api/v1/contacts/{person}", json={"phone": "000"})
        assert resp.status_code == 403
        assert "production you cannot edit" in resp.json()["detail"]
        assert "Other" not in resp.json()["detail"]  # failure case: the refusal must not name a film the caller cannot see
        assert _phone_of(client, mine, person) == "+420 777 000 111"

    def test_a_viewer_role_on_the_other_film_is_not_enough(self, client: TestClient) -> None:
        _mine, _other, person = self._shared(client, other_role="viewer")
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "000"}).status_code == 403

    def test_edit_rights_on_every_film_using_the_contact_are_enough(self, client: TestClient) -> None:
        mine, other, person = self._shared(client, other_role="editor")
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "602 111 222"}).status_code == 200
        assert _phone_of(client, mine, person) == "602 111 222"
        assert _phone_of(client, other, person) == "602 111 222"

    def test_a_cast_use_on_a_stranger_film_counts_too(self, client: TestClient) -> None:
        mine, other, person = _production(client, "Mine"), _production(client, "Other"), _contact(client)
        _on_crew(client, mine, person)
        _on_cast(client, other, person)
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "000"}).status_code == 403

    def test_someone_only_in_the_cast_of_my_film_can_be_edited(self, client: TestClient) -> None:
        mine, person = _production(client, "Mine"), _contact(client)
        _on_cast(client, mine, person)
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"name": "Jana N."}).status_code == 200

    def test_a_contact_nobody_uses_stays_editable_by_the_service_token_only(self, client: TestClient) -> None:
        person = _contact(client)
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"name": "Taken over"}).status_code == 403
        assert client.patch(f"/api/v1/contacts/{person}", json={"name": "Fixed"}, headers=AUTH).status_code == 200

    def test_the_photo_cannot_be_replaced_or_removed_either(self, client: TestClient) -> None:
        _mine, _other, person = self._shared(client, other_role=None)
        with signed_in_as(AD):
            upload = client.post(f"/api/v1/contacts/{person}/photo", files={"file": ("a.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")})
            removal = client.delete(f"/api/v1/contacts/{person}/photo")
        assert upload.status_code == 403
        assert removal.status_code == 403

    def test_the_service_token_can_edit_a_shared_contact(self, client: TestClient) -> None:
        mine, _other, person = self._shared(client, other_role=None)
        assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "602 333 444"}, headers=AUTH).status_code == 200
        assert _phone_of(client, mine, person) == "602 333 444"

"""FR-220: contact rows are shared across productions, so attaching one and editing one are both access decisions."""

import io
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import Principal, require_principal
from app.config import get_settings
from app.main import app
from app.models.production import Contact

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

    def test_an_editor_of_a_film_using_the_contact_can_reuse_it(self, client: TestClient) -> None:
        last_film, person = _production(client, "Last film"), _contact(client)
        _on_crew(client, last_film, person)
        next_film = _production(client, "Next film")
        _member(client, last_film, AD, "editor")
        _member(client, next_film, AD, "editor")
        with signed_in_as(AD):
            assert _attach_crew(client, next_film, person).status_code == 201

    def test_a_viewer_cannot_spread_a_contact_and_is_told_why(self, client: TestClient) -> None:
        """Failure case: they can see this person, so a bare 404 would be false; the reason is the useful answer."""
        their_film, person = _production(client, "Their film"), _contact(client)
        _on_crew(client, their_film, person)
        mine = _production(client, "Mine")
        _member(client, their_film, AD, "viewer")
        _member(client, mine, AD, "owner")
        with signed_in_as(AD):
            crew, cast = _attach_crew(client, mine, person), _attach_cast(client, mine, person)
        assert crew.status_code == 403 and cast.status_code == 403
        assert "add them as a new person" in crew.json()["detail"]
        assert "Their film" not in crew.json()["detail"]

    def test_a_person_removed_from_a_crew_cannot_be_taken_by_a_stranger(self, client: TestClient) -> None:
        """The bypass from review: the id stays known from old public sheets after the last crew row is gone."""
        film, person = _production(client), _contact(client)
        _on_crew(client, film, person)
        crew = client.get(f"/api/v1/productions/{film}/crew-members", headers=AUTH).json()
        assert client.delete(f"/api/v1/productions/{film}/crew-members/{crew[0]['id']}", headers=AUTH).status_code == 204
        mine = _production(client, "Mine")
        _member(client, mine, ATTACKER, "owner")
        with signed_in_as(ATTACKER):
            attach = _attach_crew(client, mine, person)
            edit = client.patch(f"/api/v1/contacts/{person}", json={"phone": "000"})
        assert attach.status_code == 404
        assert "jana@example.com" not in attach.text
        assert edit.status_code == 403

    def test_an_unused_contact_can_be_attached_by_its_creator_only(self, client: TestClient) -> None:
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        _member(client, mine, ATTACKER, "editor")
        with signed_in_as(AD):
            created = client.post("/api/v1/contacts", json={"name": "New Person", "phone": "602 000 111"})
            assert created.status_code == 201
            assert "created_by" not in created.json()
            person = created.json()["id"]
        with signed_in_as(ATTACKER):
            assert _attach_crew(client, mine, person).status_code == 404
        with signed_in_as(AD):
            assert _attach_crew(client, mine, person).status_code == 201

    def test_the_creators_right_is_spent_on_the_first_attach(self, client: TestClient, db_session) -> None:
        """Failure case: someone later edited in by others must not stay reachable through having once typed their name."""
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            person = client.post("/api/v1/contacts", json={"name": "New Person", "phone": "602 000 111"}).json()["id"]
            member = _attach_crew(client, mine, person)
            assert member.status_code == 201
            assert db_session.get(Contact, uuid.UUID(person)).created_by is None
            assert client.delete(f"/api/v1/productions/{mine}/crew-members/{member.json()['id']}").status_code == 204
            assert _attach_crew(client, mine, person).status_code == 404
        assert client.post(f"/api/v1/productions/{mine}/crew-members", json={"contact_id": person, "department": "Grip", "position": "Key grip"}, headers=AUTH).status_code == 201

    def test_the_creators_right_is_spent_on_a_cast_attach_too(self, client: TestClient, db_session) -> None:
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            person = client.post("/api/v1/contacts", json={"name": "New Actor"}).json()["id"]
            actor = _attach_cast(client, mine, person)
            assert actor.status_code == 201
            assert client.delete(f"/api/v1/productions/{mine}/cast-members/{actor.json()['id']}").status_code == 204
            assert _attach_cast(client, mine, person).status_code == 404

    def test_a_new_person_can_still_go_on_both_crew_and_cast(self, client: TestClient) -> None:
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            person = client.post("/api/v1/contacts", json={"name": "Both"}).json()["id"]
            assert _attach_crew(client, mine, person).status_code == 201
            assert _attach_cast(client, mine, person).status_code == 201

    def test_a_bulk_import_of_new_people_still_attaches_each_one(self, client: TestClient) -> None:
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            for i in range(5):
                person = client.post("/api/v1/contacts", json={"name": f"Imported {i}", "phone": f"60200000{i}"}).json()["id"]
                assert _attach_crew(client, mine, person).status_code == 201

    def test_create_then_attach_works_for_cast_too(self, client: TestClient) -> None:
        mine = _production(client, "Mine")
        _member(client, mine, AD, "editor")
        with signed_in_as(AD):
            actor = client.post("/api/v1/contacts", json={"name": "New Actor"}).json()["id"]
            assert _attach_cast(client, mine, actor).status_code == 201

    def test_the_creator_cannot_be_claimed_in_the_request(self, client: TestClient, db_session) -> None:
        with signed_in_as(ATTACKER):
            person = client.post("/api/v1/contacts", json={"name": "Spoof", "created_by": AD.label}).json()["id"]
        assert db_session.get(Contact, uuid.UUID(person)).created_by == ATTACKER.label

    def test_an_old_unused_row_with_no_creator_is_for_the_service_token_only(self, client: TestClient, db_session) -> None:
        old = Contact(name="From before", phone="602 000 222")
        db_session.add(old)
        db_session.commit()
        mine = _production(client, "Mine")
        _member(client, mine, AD, "owner")
        with signed_in_as(AD):
            assert _attach_crew(client, mine, str(old.id)).status_code == 404
        assert client.post(f"/api/v1/productions/{mine}/crew-members", json={"contact_id": str(old.id), "department": "Grip", "position": "Key grip"}, headers=AUTH).status_code == 201

    def test_the_service_token_stays_unrestricted(self, client: TestClient) -> None:
        film_a, film_b, person = _production(client), _production(client), _contact(client)
        _on_crew(client, film_a, person)
        _on_cast(client, film_b, person)


class TestSearch:
    def test_the_picker_is_told_what_the_caller_can_attach(self, client: TestClient) -> None:
        tag = "Zyxwvq"
        viewed, edited, shared = _production(client, "Viewed"), _production(client, "Edited"), _contact(client, f"Shared {tag}")
        only_viewed, only_edited = _contact(client, f"Viewed {tag}"), _contact(client, f"Edited {tag}")
        _on_crew(client, viewed, only_viewed)
        _on_crew(client, edited, only_edited)
        _on_crew(client, viewed, shared)
        _on_crew(client, edited, shared)
        _member(client, viewed, AD, "viewer")
        _member(client, edited, AD, "editor")
        with signed_in_as(AD):
            hits = {c["id"]: c["can_attach"] for c in client.get(f"/api/v1/contacts?q={tag}").json()}
        assert hits == {only_viewed: False, only_edited: True, shared: True}


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

    def test_edit_rights_on_any_film_using_the_contact_are_enough(self, client: TestClient) -> None:
        mine, other, person = self._shared(client, other_role=None)
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "602 111 222"}).status_code == 200
        assert _phone_of(client, mine, person) == "602 111 222"
        assert _phone_of(client, other, person) == "602 111 222"

    def test_a_stranger_cannot_edit(self, client: TestClient) -> None:
        film, person = _production(client), _contact(client)
        _on_crew(client, film, person)
        with signed_in_as(ATTACKER):
            resp = client.patch(f"/api/v1/contacts/{person}", json={"phone": "000"})
        assert resp.status_code == 403
        assert _phone_of(client, film, person) == "+420 777 000 111"

    def test_a_viewer_cannot_edit(self, client: TestClient) -> None:
        film, person = _production(client), _contact(client)
        _on_crew(client, film, person)
        _member(client, film, AD, "viewer")
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "000"}).status_code == 403

    def test_a_viewer_cannot_lock_the_real_editors_out(self, client: TestClient) -> None:
        """The lockout from review: a viewer used to attach the person to their own film, and editing then needed that film too."""
        film, person = _production(client, "Victim"), _contact(client)
        _on_crew(client, film, person)
        _member(client, film, AD, "owner")
        _member(client, film, ATTACKER, "viewer")
        mine = _production(client, "Mine")
        _member(client, mine, ATTACKER, "owner")
        with signed_in_as(ATTACKER):
            assert _attach_crew(client, mine, person).status_code == 403
        with signed_in_as(AD):
            assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "602 222 333"}).status_code == 200

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

    def test_the_photo_cannot_be_replaced_or_removed_by_a_stranger(self, client: TestClient) -> None:
        film, person = _production(client), _contact(client)
        _on_crew(client, film, person)
        with signed_in_as(ATTACKER):
            upload = client.post(f"/api/v1/contacts/{person}/photo", files={"file": ("a.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")})
            removal = client.delete(f"/api/v1/contacts/{person}/photo")
        assert upload.status_code == 403
        assert removal.status_code == 403

    def test_the_service_token_can_edit_any_contact(self, client: TestClient) -> None:
        mine, _other, person = self._shared(client, other_role=None)
        assert client.patch(f"/api/v1/contacts/{person}", json={"phone": "602 333 444"}, headers=AUTH).status_code == 200
        assert _phone_of(client, mine, person) == "602 333 444"

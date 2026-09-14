"""FR-15: per-production roles with least privilege (ADR-005).

Users are Supabase JWTs signed with a local ES256 key (see test_auth.py);
the service token is owner everywhere.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.config import get_settings

SERVICE = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
DAY = {"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}}


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


def test_creator_becomes_owner_and_only_members_see_the_production(client: TestClient, users) -> None:
    ada, bob = users("ada@example.com"), users("bob@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Roles"}, headers=ada).json()["id"]
    mine = client.get("/api/v1/productions", headers=ada).json()
    assert [p["id"] for p in mine] == [pid]
    assert mine[0]["my_role"] == "owner"
    assert "production:manage_members" in mine[0]["permissions"]
    assert client.get("/api/v1/productions", headers=bob).json() == []
    resp = client.get(f"/api/v1/productions/{pid}", headers=bob)
    assert resp.status_code == 403
    assert "Roles" in resp.json()["detail"]


def test_role_matrix(client: TestClient, users) -> None:
    owner, editor, viewer, stranger = users("o@example.com"), users("e@example.com"), users("v@example.com"), users("s@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Matrix"}, headers=owner).json()["id"]
    for email, role in (("e@example.com", "editor"), ("v@example.com", "viewer")):
        assert client.post(f"/api/v1/productions/{pid}/members", json={"email": email, "role": role}, headers=owner).status_code == 201

    # editor: publish yes, manage members no
    day = client.post(f"/api/v1/productions/{pid}/call-sheets", json=DAY, headers=editor)
    assert day.status_code == 201
    assert client.post(f"/api/v1/productions/{pid}/members", json={"email": "x@example.com", "role": "viewer"}, headers=editor).status_code == 403

    # viewer: read yes, publish no, crew edit no
    assert client.get(f"/api/v1/productions/{pid}/call-sheets", headers=viewer).status_code == 200
    assert client.post(f"/api/v1/productions/{pid}/call-sheets", json=DAY, headers=viewer).status_code == 403
    assert client.post(f"/api/v1/call-sheets/{day.json()['id']}/revisions", json=DAY["initial_revision"], headers=viewer).status_code == 403
    cid = client.post("/api/v1/contacts", json={"name": "N"}, headers=viewer).json()["id"]
    assert client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "AD", "position": "2nd AD"}, headers=viewer).status_code == 403

    # stranger: nothing, and the revision endpoint does not leak either
    assert client.get(f"/api/v1/productions/{pid}/call-sheets", headers=stranger).status_code == 403
    assert client.post(f"/api/v1/call-sheets/{day.json()['id']}/revisions", json=DAY["initial_revision"], headers=stranger).status_code == 403

    # my_role and permissions reflect the caller
    assert client.get(f"/api/v1/productions/{pid}", headers=viewer).json()["my_role"] == "viewer"
    assert "day:publish" not in client.get(f"/api/v1/productions/{pid}", headers=viewer).json()["permissions"]


def test_invite_by_email_binds_on_first_sign_in_and_can_be_removed(client: TestClient, users) -> None:
    owner = users("own@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Invite"}, headers=owner).json()["id"]
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "New.Person@Example.com", "role": "editor"}, headers=owner)
    newcomer = users("new.person@example.com")  # case-insensitive match
    assert client.get(f"/api/v1/productions/{pid}", headers=newcomer).json()["my_role"] == "editor"
    members = client.get(f"/api/v1/productions/{pid}/members", headers=owner).json()
    row = next(m for m in members if m["email"] == "new.person@example.com")
    assert row["user_id"] == "uid-new.person@example.com"  # bound on first authenticated request
    assert client.delete(f"/api/v1/productions/{pid}/members/{row['id']}", headers=owner).status_code == 204
    assert client.get(f"/api/v1/productions/{pid}", headers=newcomer).status_code == 403


def test_owner_cannot_remove_the_last_owner(client: TestClient, users) -> None:
    owner = users("solo@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Solo"}, headers=owner).json()["id"]
    me = client.get(f"/api/v1/productions/{pid}/members", headers=owner).json()[0]
    resp = client.delete(f"/api/v1/productions/{pid}/members/{me['id']}", headers=owner)
    assert resp.status_code == 409


def test_service_token_is_owner_everywhere(client: TestClient, users) -> None:
    owner = users("someone@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Svc"}, headers=owner).json()["id"]
    assert client.get(f"/api/v1/productions/{pid}", headers=SERVICE).json()["my_role"] == "owner"
    assert any(p["id"] == pid for p in client.get("/api/v1/productions", headers=SERVICE).json())


def test_contact_edit_is_scoped_to_productions_where_the_caller_can_edit_crew(client: TestClient, users) -> None:
    """IDOR guard: a contact can be edited only by someone with crew:edit on a production that uses it."""
    ada, bob = users("ada2@example.com"), users("bob2@example.com")
    pid_a = client.post("/api/v1/productions", json={"name": "A"}, headers=ada).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Shared Person", "phone": "+420 1"}, headers=ada).json()["id"]
    client.post(f"/api/v1/productions/{pid_a}/crew-members", json={"contact_id": cid, "department": "AD", "position": "2nd AD"}, headers=ada)
    # bob owns another production but is not on A: cannot touch A's contact
    client.post("/api/v1/productions", json={"name": "B"}, headers=bob)
    assert client.patch(f"/api/v1/contacts/{cid}", json={"phone": "+420 hijacked"}, headers=bob).status_code == 403
    # a viewer on A cannot either
    client.post(f"/api/v1/productions/{pid_a}/members", json={"email": "bob2@example.com", "role": "viewer"}, headers=ada)
    assert client.patch(f"/api/v1/contacts/{cid}", json={"phone": "+420 hijacked"}, headers=bob).status_code == 403
    # the owner can
    assert client.patch(f"/api/v1/contacts/{cid}", json={"phone": "+420 2"}, headers=ada).json()["phone"] == "+420 2"
    # a contact used by no production is editable by nobody but the service token
    loose = client.post("/api/v1/contacts", json={"name": "Loose"}, headers=ada).json()["id"]
    assert client.patch(f"/api/v1/contacts/{loose}", json={"name": "x"}, headers=ada).status_code == 403
    assert client.patch(f"/api/v1/contacts/{loose}", json={"name": "x"}, headers=SERVICE).status_code == 200

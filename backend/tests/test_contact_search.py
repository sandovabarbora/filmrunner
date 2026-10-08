"""FR-45: reuse people across productions — who the caller may pick."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}

# The service token sees every contact in the database, including leftovers from an E2E run
# against the same test database, so every name here carries a per-test tag.
import uuid


def _tag() -> str:
    # Letters only: the search also matches the digits of a query against phone numbers, so a hex tag's digits
    # could hit another contact's phone and make a name query flaky.
    return "".join(chr(ord("a") + int(c, 16)) for c in uuid.uuid4().hex[:6])


def _production(client: TestClient, name: str) -> str:
    return client.post("/api/v1/productions", json={"name": name}, headers=AUTH).json()["id"]


def _crew(client: TestClient, pid: str, name: str, phone: str | None, position: str = "Gaffer") -> dict:
    cid = client.post("/api/v1/contacts", json={"name": name, "phone": phone}, headers=AUTH).json()["id"]
    return client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Electric", "position": position}, headers=AUTH).json()


def test_matches_name_prefix_any_word_and_phone_digits_with_last_production(client: TestClient) -> None:
    t = _tag()
    d = f"{uuid.uuid4().int % 1000:03d}"
    a = _production(client, "Alpha")
    _crew(client, a, f"Tomáš Novák{t}", f"+420 777 {d} 456")
    _crew(client, a, f"Petra Nováková{t}", "602 000 111", position="Best boy")
    _crew(client, a, f"Jan Dvořák{t}", None)

    names = lambda q: [c["name"] for c in client.get(f"/api/v1/contacts?q={q}", headers=AUTH).json() if c["name"].endswith(t)]
    assert names(f"novák{t}") == [f"Tomáš Novák{t}"]  # any word
    assert names(f"nováková{t}") == [f"Petra Nováková{t}"]
    assert names(f"tomáš novák{t}") == [f"Tomáš Novák{t}"]
    assert names(f"777{d}456") == [f"Tomáš Novák{t}"]  # phone digits
    assert client.get("/api/v1/contacts?q=t", headers=AUTH).json() == []  # too short to be useful
    hit = next(c for c in client.get(f"/api/v1/contacts?q=petra nováková{t}", headers=AUTH).json() if c["name"].endswith(t))
    assert hit["last_production_name"] == "Alpha" and hit["last_position"] == "Best boy"


def test_same_name_different_phone_stays_two_people(client: TestClient) -> None:
    """Failure case: never merged; both shown with their numbers."""
    t = _tag()
    a = _production(client, "Alpha")
    _crew(client, a, f"Jan Novák{t}", "777 111 111")
    _crew(client, _production(client, "Beta"), f"Jan Novák{t}", "777 222 222")
    hits = [h for h in client.get(f"/api/v1/contacts?q=jan novák{t}", headers=AUTH).json() if h["name"].endswith(t)]
    assert [h["phone"] for h in hits] == ["777 111 111", "777 222 222"]
    assert len({h["id"] for h in hits}) == 2


def test_a_member_sees_only_contacts_on_their_productions(client: TestClient) -> None:
    from app.auth import Principal
    from app.main import app
    from app.auth import require_principal

    a = _production(client, "Alpha")
    b = _production(client, "Beta")
    t = _tag()
    _crew(client, a, f"Only Alpha{t}", "777 000 001")
    _crew(client, b, f"Only Beta{t}", "777 000 002")
    client.post(f"/api/v1/productions/{a}/members", json={"email": "viewer@example.com", "role": "viewer"}, headers=AUTH)

    viewer = Principal(kind="user", subject="user-viewer", email="viewer@example.com")
    app.dependency_overrides[require_principal] = lambda: viewer
    try:
        hits = client.get("/api/v1/contacts?q=only").json()
    finally:
        app.dependency_overrides.pop(require_principal, None)
    assert [h["name"] for h in hits if h["name"].endswith(t)] == [f"Only Alpha{t}"]

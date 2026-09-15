"""FR-18: crew avatar upload to Supabase Storage.

The test environment has no Supabase Storage credentials configured (same as
this app's real deployment until INBOX's bucket item is done), so the
"happy path" upload is exercised against a monkeypatched storage call; the
unconfigured 503 path is exercised for real, against the actual default
settings, since that's exactly the state production is in today.
"""

import io

import pytest
from fastapi.testclient import TestClient

import app.routers.productions as productions_router
from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 100  # not a real decodable JPEG; content-type is what the API checks


def _crew_member(client: TestClient) -> tuple[str, str, str]:
    pid = client.post("/api/v1/productions", json={"name": "Photo test"}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Petr Malý", "phone": "+420 602 000 000"}, headers=AUTH).json()["id"]
    member = client.post(
        f"/api/v1/productions/{pid}/crew-members",
        json={"contact_id": cid, "department": "Camera", "position": "1st AC"},
        headers=AUTH,
    ).json()
    return pid, cid, member["id"]


def test_upload_without_storage_configured_returns_503(client: TestClient) -> None:
    """Real default settings: no supabase_service_role_key. This is production's actual state today."""
    _pid, cid, _mid = _crew_member(client)
    resp = client.post(
        f"/api/v1/contacts/{cid}/photo",
        files={"file": ("avatar.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers=AUTH,
    )
    assert resp.status_code == 503
    assert "INBOX" in resp.json()["detail"]


def test_upload_rejects_wrong_content_type(client: TestClient) -> None:
    _pid, cid, _mid = _crew_member(client)
    resp = client.post(
        f"/api/v1/contacts/{cid}/photo",
        files={"file": ("avatar.gif", io.BytesIO(b"GIF89a"), "image/gif")},
        headers=AUTH,
    )
    assert resp.status_code == 415


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    _pid, cid, _mid = _crew_member(client)
    oversized = b"0" * 400_000
    resp = client.post(
        f"/api/v1/contacts/{cid}/photo",
        files={"file": ("avatar.jpg", io.BytesIO(oversized), "image/jpeg")},
        headers=AUTH,
    )
    assert resp.status_code == 413


def test_upload_unknown_contact_is_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/contacts/00000000-0000-0000-0000-000000000000/photo",
        files={"file": ("avatar.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers=AUTH,
    )
    assert resp.status_code == 404


def test_upload_success_sets_photo_url_and_appears_in_who_to_call(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(productions_router, "upload_contact_photo", lambda contact_id, data, content_type: f"https://stub.supabase.co/storage/v1/object/public/avatars/{contact_id}.jpg?v=abc123")
    pid, cid, mid = _crew_member(client)
    client.patch(f"/api/v1/productions/{pid}/crew-members/{mid}", json={"is_head_of_department": True}, headers=AUTH)

    resp = client.post(
        f"/api/v1/contacts/{cid}/photo",
        files={"file": ("avatar.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers=AUTH,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["photo_url"] == f"https://stub.supabase.co/storage/v1/object/public/avatars/{cid}.jpg?v=abc123"

    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"schedule_items": []}},
        headers=AUTH,
    ).json()
    contacts = client.get(f"/api/v1/public/call-sheets/{sheet['id']}").json()["contacts"]
    assert contacts["department_heads"][0]["photo_url"].startswith("https://stub.supabase.co/")


def test_upload_failure_does_not_touch_other_fields(client: TestClient) -> None:
    """A failed photo upload (503, unconfigured) must never roll back or block a field already saved."""
    pid, cid, mid = _crew_member(client)
    client.patch(f"/api/v1/contacts/{cid}", json={"phone": "+420 777 000 111"}, headers=AUTH)
    resp = client.post(
        f"/api/v1/contacts/{cid}/photo",
        files={"file": ("avatar.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers=AUTH,
    )
    assert resp.status_code == 503
    crew = client.get(f"/api/v1/productions/{pid}/crew-members", headers=AUTH).json()
    member = next(m for m in crew if m["id"] == mid)
    assert member["contact"]["phone"] == "+420 777 000 111"
    assert member["contact"]["photo_url"] is None


def test_remove_photo_clears_it(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(productions_router, "upload_contact_photo", lambda contact_id, data, content_type: "https://stub.supabase.co/x.jpg")
    _pid, cid, _mid = _crew_member(client)
    client.post(f"/api/v1/contacts/{cid}/photo", files={"file": ("a.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}, headers=AUTH)
    resp = client.delete(f"/api/v1/contacts/{cid}/photo", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["photo_url"] is None



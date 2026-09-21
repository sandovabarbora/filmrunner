"""Crew photos stored in Postgres (no bucket, no service-role key)."""

import io

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6364f8cfc0000002030101f0d1a06d0000000049454e44ae426082")


def _contact_in_crew(client: TestClient) -> str:
    pid = client.post("/api/v1/productions", json={"name": "Photo DB"}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Foto Osoba"}, headers=AUTH).json()["id"]
    client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": cid, "department": "Camera", "position": "DoP"}, headers=AUTH)
    return cid


def test_upload_stores_in_db_and_serves_publicly(client: TestClient) -> None:
    cid = _contact_in_crew(client)
    resp = client.post(f"/api/v1/contacts/{cid}/photo", files={"file": ("me.png", io.BytesIO(PNG), "image/png")}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    url = resp.json()["photo_url"]
    assert f"/api/v1/public/contacts/{cid}/photo?v=" in url
    path = url.split(get_settings().public_base_url.rstrip("/"), 1)[1]
    got = client.get(path)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.content == PNG
    assert "max-age" in got.headers.get("cache-control", "")


def test_reupload_changes_the_version_and_delete_removes_it(client: TestClient) -> None:
    cid = _contact_in_crew(client)
    first = client.post(f"/api/v1/contacts/{cid}/photo", files={"file": ("a.png", io.BytesIO(PNG), "image/png")}, headers=AUTH).json()["photo_url"]
    second = client.post(f"/api/v1/contacts/{cid}/photo", files={"file": ("b.png", io.BytesIO(PNG), "image/png")}, headers=AUTH).json()["photo_url"]
    assert first != second  # cache-busting version changes
    assert client.delete(f"/api/v1/contacts/{cid}/photo", headers=AUTH).json()["photo_url"] is None
    assert client.get(f"/api/v1/public/contacts/{cid}/photo").status_code == 404


def test_missing_photo_is_404_not_500(client: TestClient) -> None:
    assert client.get("/api/v1/public/contacts/00000000-0000-0000-0000-000000000000/photo").status_code == 404

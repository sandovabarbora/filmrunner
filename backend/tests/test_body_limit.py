"""FR-220: bodies are parsed before auth runs, so an open endpoint on a 256 MB machine needs a cap in front of it."""

import asyncio
import io
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.bodylimit import DEFAULT_LIMIT, UPLOAD_LIMIT, BodyLimitMiddleware
from app.config import get_settings
from app.main import app

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
ORIGIN = {"Origin": "https://sheet.example"}
ANY_ID = "00000000-0000-4000-8000-000000000000"
CONTACTS = "/api/v1/contacts"
CHUNK = 64 * 1024


def _chunks(total: int):
    while total > 0:
        yield b"x" * min(CHUNK, total)
        total -= CHUNK


def _drive(asgi_app, path: str, headers: list[tuple[bytes, bytes]], chunks) -> tuple[int, dict[bytes, bytes], int]:
    """Feed a body chunk by chunk, as a slow client would, and report how many chunks were pulled."""
    pulled = 0
    source = iter(chunks)
    sent: list[dict] = []

    async def receive() -> dict:
        nonlocal pulled
        chunk = next(source, None)
        if chunk is None:
            return {"type": "http.request", "body": b"", "more_body": False}
        pulled += 1
        return {"type": "http.request", "body": chunk, "more_body": True}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "path": path, "raw_path": path.encode(),
             "root_path": "", "scheme": "http", "query_string": b"", "headers": headers, "client": ("1.2.3.4", 1), "server": ("test", 80)}
    asyncio.run(asgi_app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"], dict(start["headers"]), pulled


class TestDeclaredLength:
    def test_an_ordinary_route_refuses_over_256_kb_before_auth(self, client: TestClient) -> None:
        resp = client.post(CONTACTS, content=b"x" * (DEFAULT_LIMIT + 1), headers={"content-type": "application/json"})
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]

    def test_exactly_the_limit_is_let_through(self, client: TestClient) -> None:
        resp = client.post(CONTACTS, content=b"x" * DEFAULT_LIMIT, headers={"content-type": "application/json"})
        assert resp.status_code != 413

    def test_the_browser_can_read_the_413(self, client: TestClient) -> None:
        """Failure case: without CORS headers the editor sees a blocked request, not the message."""
        resp = client.post(CONTACTS, content=b"x" * (DEFAULT_LIMIT + 1), headers=ORIGIN)
        assert resp.status_code == 413
        assert resp.headers["access-control-allow-origin"]

    def test_the_public_routes_are_capped_too(self, client: TestClient) -> None:
        resp = client.post("/api/v1/public/crew/tok/push-subscription", content=b"x" * (DEFAULT_LIMIT + 1))
        assert resp.status_code == 413

    @pytest.mark.parametrize("path", [f"/api/v1/productions/{ANY_ID}/import/call-sheet-pdf", f"/api/v1/contacts/{ANY_ID}/photo"])
    def test_the_upload_routes_allow_12_mb_and_no_more(self, client: TestClient, path: str) -> None:
        within = client.post(path, content=b"x" * (DEFAULT_LIMIT + 1), headers={"content-type": "application/json"})
        assert within.status_code != 413
        over = client.post(path, content=b"x" * (UPLOAD_LIMIT + 1), headers=ORIGIN)
        assert over.status_code == 413
        assert over.headers["access-control-allow-origin"]

    def test_the_upload_allowance_does_not_reach_neighbouring_routes(self, client: TestClient) -> None:
        for path in (f"/api/v1/contacts/{ANY_ID}", f"/api/v1/productions/{ANY_ID}/crew-members", f"/api/v1/contacts/{ANY_ID}/photo/extra"):
            assert client.post(path, content=b"x" * (DEFAULT_LIMIT + 1)).status_code == 413, path

    def test_a_nonsense_content_length_falls_back_to_counting(self) -> None:
        status, _headers, _pulled = _drive(app, CONTACTS, [(b"content-length", b"banana"), (b"content-type", b"application/json")], _chunks(DEFAULT_LIMIT * 2))
        assert status == 413


class TestStreamedBody:
    def test_no_content_length_is_counted(self, client: TestClient) -> None:
        resp = client.post(CONTACTS, content=_chunks(DEFAULT_LIMIT + 1), headers=ORIGIN)
        assert "content-length" not in resp.request.headers
        assert resp.status_code == 413
        assert resp.headers["access-control-allow-origin"]

    def test_a_content_length_that_lies_is_counted(self, client: TestClient) -> None:
        resp = client.post(CONTACTS, content=b"x" * (DEFAULT_LIMIT + 1), headers={"content-length": "10"})
        assert resp.status_code == 413

    def test_reading_stops_at_the_limit_instead_of_buffering_the_rest(self) -> None:
        status, headers, pulled = _drive(app, CONTACTS, [(b"content-type", b"application/json"), (b"origin", b"https://sheet.example")], _chunks(DEFAULT_LIMIT * 100))
        assert status == 413
        assert b"access-control-allow-origin" in headers
        assert pulled * CHUNK <= DEFAULT_LIMIT + CHUNK

    def test_a_multipart_upload_with_no_length_stops_at_12_mb(self) -> None:
        boundary = b"fr220"
        head = b"--" + boundary + b'\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
        status, headers, pulled = _drive(
            app, f"/api/v1/productions/{ANY_ID}/import/call-sheet-pdf",
            [(b"content-type", b"multipart/form-data; boundary=" + boundary), (b"origin", b"https://sheet.example")],
            [head, *_chunks(UPLOAD_LIMIT * 2)],
        )
        assert status == 413
        assert b"access-control-allow-origin" in headers
        assert pulled * CHUNK <= UPLOAD_LIMIT + 2 * CHUNK

    def test_a_body_under_the_limit_reaches_the_route_whole(self) -> None:
        inner = FastAPI()

        @inner.post("/echo")
        async def echo(request: Request) -> dict[str, int]:
            return {"size": len(await request.body())}

        inner.add_middleware(BodyLimitMiddleware)
        with TestClient(inner) as small_client:
            resp = small_client.post("/echo", content=_chunks(DEFAULT_LIMIT))
        assert resp.json() == {"size": DEFAULT_LIMIT}


class TestBoundedRead:
    def _film(self, client: TestClient) -> str:
        return client.post("/api/v1/productions", json={"name": "Limits"}, headers=AUTH).json()["id"]

    def test_a_pdf_over_its_own_10_mb_limit_is_refused_with_its_own_message(self, client: TestClient) -> None:
        resp = client.post(f"/api/v1/productions/{self._film(client)}/import/call-sheet-pdf",
                           files={"file": ("big.pdf", io.BytesIO(b"%PDF" + b"0" * (11 * 1000 * 1000)), "application/pdf")}, headers=AUTH)
        assert resp.status_code == 413
        assert "10 MB" in resp.json()["detail"]

    def test_the_pdf_handler_asks_for_no_more_than_one_byte_past_its_limit(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from starlette.datastructures import UploadFile

        from app.services.call_sheet_pdf import MAX_PDF_BYTES

        asked: list[int] = []
        real_read = UploadFile.read

        async def spy(self, size: int = -1) -> bytes:
            asked.append(size)
            return await real_read(self, size)

        monkeypatch.setattr(UploadFile, "read", spy)
        client.post(f"/api/v1/productions/{self._film(client)}/import/call-sheet-pdf",
                    files={"file": ("x.pdf", io.BytesIO(b"not a pdf"), "application/pdf")}, headers=AUTH)
        assert asked == [MAX_PDF_BYTES + 1]


def test_a_very_large_day_publishes_under_the_cap(client: TestClient) -> None:
    """Failure case: the cap must never bite a real day, so this one is well past a real shooting day's size."""
    pid = client.post("/api/v1/productions", json={"name": "Big day"}, headers=AUTH).json()["id"]
    contact_ids = [client.post("/api/v1/contacts", json={"name": f"Person {i}"}, headers=AUTH).json()["id"] for i in range(120)]
    crew_ids = [
        client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": c, "department": "Grip", "position": "Key grip"}, headers=AUTH).json()["id"]
        for c in contact_ids
    ]
    body = {
        "shoot_date": "2026-12-01", "day_number": 1, "day_count": 30,
        "initial_revision": {
            "general_crew_call": "06:30", "safety_notes": "Mokrá podlaha u nádrže. " * 40, "weather_forecast": "Déšť od 15:00. " * 20,
            "schedule_items": [
                {"order_index": i, "scene_number": f"{i}A", "int_ext": "INT", "day_night": "DAY", "set_description": "Byt v Holešovicích, kuchyně a chodba, " * 3, "page_count_eighths": 8}
                for i in range(100)
            ],
            "crew_calls": [{"crew_member_id": m, "call_time": "06:30", "pickup_time": "05:45", "note": "Parkování za domem, vjezd z boku. " * 2} for m in crew_ids],
        },
    }
    resp = client.post(f"/api/v1/productions/{pid}/call-sheets", json=body, headers=AUTH)
    assert resp.status_code == 201, resp.text


def test_no_413_depends_on_a_starlette_status_constant() -> None:
    """The constant's name changed between Starlette versions, and using a missing one only fails when a 413 is due."""
    backend = Path(__file__).resolve().parents[1] / "app"
    for module in (backend / "bodylimit.py", backend / "routers" / "productions.py"):
        assert "HTTP_413" not in module.read_text(), module

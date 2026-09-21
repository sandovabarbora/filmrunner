"""FR-57: contacts out of an old call sheet PDF."""

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import call_sheet_pdf

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}
FIXTURES = Path(__file__).parent / "fixtures"


def test_heuristics_read_a_czech_and_an_english_layout() -> None:
    cz, _ = call_sheet_pdf.extract_text((FIXTURES / "call-sheet-cz.pdf").read_bytes())
    got = [(c.name, c.department, c.position, c.phone) for c in call_sheet_pdf.heuristics(cz)]
    assert got == [
        ("Eva Dvořáková", "REŽIE", "1. asistent režie", "+420 777 111 222"),
        ("Marta Pokorná", "REŽIE", "2. asistent režie", "605 333 444"),
        ("Marek Sýkora", "KAMERA", "Kameraman", "603 555 010"),
        ("Petra Králová", "KAMERA", "1. asistent kamery", "602 111 222"),
        ("Tomáš Novák", "OSVĚTLOVAČI", "Hlavní osvětlovač", "601 234 567"),
        ("Jana Bílá", "PRODUKCE", "Vedoucí produkce", "606 444 555"),
    ]  # the hospital line with its phone number is not a person
    en, _ = call_sheet_pdf.extract_text((FIXTURES / "call-sheet-en.pdf").read_bytes())
    got = [(c.name, c.department, c.position) for c in call_sheet_pdf.heuristics(en)]
    assert got == [("Eva Dvorakova", "ASSISTANT DIRECTORS", "1st AD"), ("Marek Sykora", "CAMERA", "DoP"),
                   ("Petra Kralova", "CAMERA", "1st AC"), ("Tomas Novak", "ELECTRIC", "Gaffer")]


def _claude_client(answer: str, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key" and request.headers["anthropic-version"]
        body = json.loads(request.content)
        assert body["temperature"] == 0 and "CALL SHEET TEXT" in body["messages"][0]["content"]
        return httpx.Response(status, json={"content": [{"type": "text", "text": answer}]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_claude_path_is_used_when_configured_and_falls_back_when_it_fails(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    data = (FIXTURES / "call-sheet-cz.pdf").read_bytes()
    good = _claude_client('Here you go:\n{"contacts": [{"name": "Eva Dvořáková", "department": "Režie", "position": "1. AD", "phone": "+420 777 111 222", "email": null},'
                          ' {"name": "", "phone": "1"}, {"name": "Bez Čísla", "department": null, "position": null, "phone": "12", "email": null}]}')
    result = call_sheet_pdf.extract_contacts(data, client=good)
    assert result.method == "claude"
    assert [(c.name, c.phone) for c in result.contacts] == [("Eva Dvořáková", "+420 777 111 222"), ("Bez Čísla", None)]
    assert 'phone "12" does not look like a number' in result.contacts[1].warnings and "no position found" in result.contacts[1].warnings

    down = _claude_client("overloaded", status=529)
    result = call_sheet_pdf.extract_contacts(data, client=down)
    assert result.method == "heuristics" and len(result.contacts) == 6
    assert any("plain-text pass" in w for w in result.warnings)


def test_endpoint_previews_and_refuses_non_pdfs_and_scans(client: TestClient) -> None:
    pid = client.post("/api/v1/productions", json={"name": "PDF"}, headers=AUTH).json()["id"]
    r = client.post(f"/api/v1/productions/{pid}/import/call-sheet-pdf", files={"file": ("cs.pdf", (FIXTURES / "call-sheet-cz.pdf").read_bytes(), "application/pdf")}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["method"] == "heuristics" and body["pages"] == 1 and len(body["contacts"]) == 6
    assert body["contacts"][0]["name"] == "Eva Dvořáková"
    assert client.get(f"/api/v1/productions/{pid}/crew-members", headers=AUTH).json() == []  # a preview creates nothing

    r = client.post(f"/api/v1/productions/{pid}/import/call-sheet-pdf", files={"file": ("x.pdf", b"hello", "application/pdf")}, headers=AUTH)
    assert r.status_code == 422 and "not a PDF" in r.json()["detail"]
    # a real PDF with no text layer (what a scan or a photo export looks like to pypdf)
    r = client.post(f"/api/v1/productions/{pid}/import/call-sheet-pdf", files={"file": ("scan.pdf", (FIXTURES / "blank.pdf").read_bytes(), "application/pdf")}, headers=AUTH)
    assert r.status_code == 422 and "no text layer" in r.json()["detail"]

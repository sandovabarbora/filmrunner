"""FR-65: actual times per day — the production's numbers, never the crew's sheet."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _day(client: TestClient, pid: str, n: int, draft: bool = False) -> dict:
    return client.post(f"/api/v1/productions/{pid}/call-sheets", json={
        "shoot_date": f"2026-09-2{n}", "day_number": n, "day_count": 3, "draft": draft,
        "initial_revision": {"general_crew_call": "06:30", "schedule_items": []},
    }, headers=AUTH).json()


def test_actuals_are_set_on_a_published_day_listed_and_kept_off_the_public_sheet(client: TestClient) -> None:
    pid = client.post("/api/v1/productions", json={"name": "Actuals"}, headers=AUTH).json()["id"]
    day = _day(client, pid, 1)
    r = client.put(f"/api/v1/call-sheets/{day['id']}/actuals", json={"first_shot": " 08:12 ", "wrap": "19:40", "note": "Rain from 15:00"}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["actuals"] == {"first_shot": "08:12", "lunch_out": None, "lunch_in": None, "wrap": "19:40", "note": "Rain from 15:00"}
    assert r.json()["current_revision"]["revision_letter"] == "A"  # no revision, no push
    listed = client.get(f"/api/v1/productions/{pid}/call-sheets", headers=AUTH).json()[0]
    assert listed["actuals"]["wrap"] == "19:40"
    assert client.get(f"/api/v1/public/call-sheets/{day['id']}").json()["actuals"] is None
    assert client.get(f"/api/v1/call-sheets/{day['id']}", headers=AUTH).json()["actuals"]["first_shot"] == "08:12"


def test_actuals_refused_on_a_draft_or_cancelled_day(client: TestClient) -> None:
    """Failure case: a draft has not happened; a cancelled day did not."""
    pid = client.post("/api/v1/productions", json={"name": "Actuals"}, headers=AUTH).json()["id"]
    draft = _day(client, pid, 2, draft=True)
    r = client.put(f"/api/v1/call-sheets/{draft['id']}/actuals", json={"wrap": "19:00"}, headers=AUTH)
    assert r.status_code == 409 and "draft" in r.json()["detail"]
    cancelled = _day(client, pid, 3)
    client.post(f"/api/v1/call-sheets/{cancelled['id']}/cancel", headers=AUTH)
    r = client.put(f"/api/v1/call-sheets/{cancelled['id']}/actuals", json={"wrap": "19:00"}, headers=AUTH)
    assert r.status_code == 409 and "cancelled" in r.json()["detail"]


def test_who_published_is_kept_off_the_public_sheet(client: TestClient) -> None:
    """FR-220: `created_by` is the AD's email for a signed-in publisher, and the public sheet needs no login."""
    from app.auth import Principal, require_principal
    from app.main import app

    ad = Principal(kind="user", subject="user-ad", email="first.ad@example.com")
    app.dependency_overrides[require_principal] = lambda: ad
    try:
        pid = client.post("/api/v1/productions", json={"name": "Who"}).json()["id"]
        day = _day(client, pid, 1)
        assert client.get(f"/api/v1/call-sheets/{day['id']}").json()["current_revision"]["created_by"] == ad.email
    finally:
        app.dependency_overrides.pop(require_principal, None)
    public = client.get(f"/api/v1/public/call-sheets/{day['id']}")
    assert public.json()["current_revision"]["created_by"] is None
    assert ad.email not in public.text

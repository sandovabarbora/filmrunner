"""FR-143: a personal crew-link token minted for one production must be
rejected (404, never a 200 with someone else's data) against every other
production's routes — the only thing standing between a leaked URL and a
stranger's phone (FR-129's own words).

`test_personal.py` and `test_seen.py` already each cover one direction of
this for their own route; this file is the single place that sweeps every
public route combining a `{token}` with a production-scoped resource id,
in both directions, so a future new route is added to one list and gets
the same guarantee automatically.
"""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _make_production(client: TestClient, name: str):
    pid = client.post("/api/v1/productions", json={"name": name}, headers=AUTH).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": f"{name} Crew", "phone": "+420 777 000 000"}, headers=AUTH).json()["id"]
    member = client.post(
        f"/api/v1/productions/{pid}/crew-members",
        json={"contact_id": cid, "department": "Camera", "position": "1st AC"},
        headers=AUTH,
    ).json()
    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-09-22", "day_number": 1, "day_count": 1, "initial_revision": {"general_crew_call": "06:30", "schedule_items": []}},
        headers=AUTH,
    ).json()
    return pid, member, sheet


# (route name, request fn(sheet, token) -> response, ok status for a genuine token)
def _get_me(client, sheet, token):
    return client.get(f"/api/v1/public/call-sheets/{sheet['id']}/me/{token}")


def _post_seen(client, sheet, token):
    return client.post(f"/api/v1/public/call-sheets/{sheet['id']}/seen/{token}")


ROUTES = [
    ("GET /public/call-sheets/{id}/me/{token}", _get_me, 200),
    ("POST /public/call-sheets/{id}/seen/{token}", _post_seen, 204),
]


def test_a_genuine_token_works_on_its_own_production(client: TestClient) -> None:
    """Sanity check the fixtures and the routes themselves before testing the cross-production rejection below."""
    _, member, sheet = _make_production(client, "A")
    for name, call, ok_status in ROUTES:
        resp = call(client, sheet, member["personal_token"])
        assert resp.status_code == ok_status, f"{name}: own token should succeed, got {resp.status_code}"


def test_every_public_token_route_rejects_a_token_from_another_production(client: TestClient) -> None:
    pid_a, member_a, sheet_a = _make_production(client, "A")
    pid_b, member_b, sheet_b = _make_production(client, "B")
    assert pid_a != pid_b

    for name, call, _ok_status in ROUTES:
        resp_a_on_b = call(client, sheet_b, member_a["personal_token"])
        assert resp_a_on_b.status_code == 404, f"{name}: production A's token against production B's resource should be 404, got {resp_a_on_b.status_code}"

        resp_b_on_a = call(client, sheet_a, member_b["personal_token"])
        assert resp_b_on_a.status_code == 404, f"{name}: production B's token against production A's resource should be 404, got {resp_b_on_a.status_code}"


def test_an_unknown_token_is_also_404_not_an_empty_200(client: TestClient) -> None:
    _, _, sheet = _make_production(client, "A")
    for name, call, _ok_status in ROUTES:
        resp = call(client, sheet, "not-a-real-token")
        assert resp.status_code == 404, f"{name}: unknown token should be 404, got {resp.status_code}"

"""FR-181: `wrapped_at` tracks the most recent WRAPPED transition, not just
whether a production currently is one, so retention can be measured from a
real wrap time instead of row age."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Wrapped-at test"}, headers=AUTH).json()["id"]


def _get(client: TestClient, pid: str) -> dict:
    r = client.get(f"/api/v1/productions/{pid}", headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def test_wrapped_at_is_none_until_the_production_wraps(client: TestClient) -> None:
    pid = _production(client)
    assert _get(client, pid)["wrapped_at"] is None

    r = client.patch(f"/api/v1/productions/{pid}", json={"status": "shooting"}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["wrapped_at"] is None


def test_wrapping_sets_wrapped_at_and_unwrapping_clears_it(client: TestClient) -> None:
    pid = _production(client)

    wrapped = client.patch(f"/api/v1/productions/{pid}", json={"status": "wrapped"}, headers=AUTH).json()
    assert wrapped["status"] == "wrapped"
    assert wrapped["wrapped_at"] is not None

    unwrapped = client.patch(f"/api/v1/productions/{pid}", json={"status": "shooting"}, headers=AUTH).json()
    assert unwrapped["status"] == "shooting"
    assert unwrapped["wrapped_at"] is None


def test_wrapping_again_after_unwrapping_moves_wrapped_at_to_the_second_wrap(client: TestClient) -> None:
    """The failure case named in FR-181's own dod: a WRAPPED -> SHOOTING -> WRAPPED
    round trip must end up timestamped at the *second* wrap, not the first — a
    report that silently measured from a stale first wrap would under-count
    how long data has actually been retained since the real, current wrap."""
    pid = _production(client)

    first_wrap = client.patch(f"/api/v1/productions/{pid}", json={"status": "wrapped"}, headers=AUTH).json()
    first_wrapped_at = first_wrap["wrapped_at"]
    assert first_wrapped_at is not None

    reopened = client.patch(f"/api/v1/productions/{pid}", json={"status": "shooting"}, headers=AUTH).json()
    assert reopened["wrapped_at"] is None

    second_wrap = client.patch(f"/api/v1/productions/{pid}", json={"status": "wrapped"}, headers=AUTH).json()
    second_wrapped_at = second_wrap["wrapped_at"]
    assert second_wrapped_at is not None
    assert second_wrapped_at != first_wrapped_at
    assert second_wrapped_at > first_wrapped_at


def test_a_no_op_status_patch_does_not_disturb_wrapped_at(client: TestClient) -> None:
    """Re-sending the same status (e.g. a form re-submit) is not a transition
    and must not reset the wrap timestamp to "now"."""
    pid = _production(client)
    wrapped = client.patch(f"/api/v1/productions/{pid}", json={"status": "wrapped"}, headers=AUTH).json()
    wrapped_at = wrapped["wrapped_at"]

    same = client.patch(f"/api/v1/productions/{pid}", json={"status": "wrapped", "name": "Wrapped-at test"}, headers=AUTH).json()
    assert same["wrapped_at"] == wrapped_at

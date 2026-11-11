"""FR-228: an actor's agreed days, with evidence, and the check of a day against them."""

from fastapi.testclient import TestClient

from app.config import get_settings

AUTH = {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


def _production(client: TestClient) -> str:
    return client.post("/api/v1/productions", json={"name": "Agreed days"}, headers=AUTH).json()["id"]


def _actor(client: TestClient, pid: str, name: str, character: str) -> dict:
    cid = client.post("/api/v1/contacts", json={"name": name}, headers=AUTH).json()["id"]
    r = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": cid, "character_name": character}, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def _agree(client: TestClient, pid: str, actor: dict, days: list[str], **evidence) -> dict:
    body = {"days": days, "agreed_by": "agent", "agreed_via": "email", "agreed_on": "2026-11-01", **evidence}
    r = client.post(f"/api/v1/productions/{pid}/cast-members/{actor['id']}/agreements", json=body, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()


def _check(client: TestClient, pid: str, checks: list[dict]):
    return client.post(f"/api/v1/productions/{pid}/cast-availability", json={"checks": checks}, headers=AUTH)


def test_an_agreement_keeps_its_evidence_and_dedupes_days(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    a = _agree(client, pid, petr, ["2026-12-15", "2026-12-14", "2026-12-14"], agreed_by="agent", agreed_via="phone", note="via agency")
    assert a["days"] == ["2026-12-14", "2026-12-15"]
    assert (a["agreed_by"], a["agreed_via"], a["agreed_on"], a["note"]) == ("agent", "phone", "2026-11-01", "via agency")
    assert a["created_by"] and a["withdrawn_at"] is None


def test_a_day_inside_the_agreed_days_raises_nothing(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    _agree(client, pid, petr, ["2026-12-14", "2026-12-15"])
    r = _check(client, pid, [{"shoot_date": "2026-12-14", "cast_member_ids": [petr["id"]]}])
    assert r.status_code == 200 and r.json() == []


def test_a_move_off_the_agreed_days_names_the_actor_and_their_days(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    _agree(client, pid, petr, ["2026-12-14"])
    _agree(client, pid, petr, ["2026-12-15"], agreed_by="actor")
    [issue] = _check(client, pid, [{"shoot_date": "2026-12-17", "cast_member_ids": [petr["id"]]}]).json()
    assert issue == {"shoot_date": "2026-12-17", "cast_member_id": petr["id"], "name": "Petr Novák", "character_name": "OTEC",
                     "status": "outside", "agreed_days": ["2026-12-14", "2026-12-15"]}


def test_no_agreed_days_is_reported_as_not_entered_never_as_fine(client: TestClient) -> None:
    """Failure case: missing evidence must not read as a clean OK."""
    pid = _production(client)
    anna = _actor(client, pid, "Anna Geislerová", "MARTA")
    [issue] = _check(client, pid, [{"shoot_date": "2026-12-14", "cast_member_ids": [anna["id"]]}]).json()
    assert issue["status"] == "not_entered" and issue["agreed_days"] == []


def test_a_withdrawn_agreement_stops_counting_but_stays_in_the_history(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    old = _agree(client, pid, petr, ["2026-12-14"])
    new = _agree(client, pid, petr, ["2026-12-20"])
    url = f"/api/v1/productions/{pid}/cast-members/{petr['id']}/agreements"
    first = client.post(f"{url}/{old['id']}/withdraw", headers=AUTH).json()
    assert first["withdrawn_at"] and first["withdrawn_by"]
    again = client.post(f"{url}/{old['id']}/withdraw", headers=AUTH).json()
    assert again["withdrawn_at"] == first["withdrawn_at"]

    [issue] = _check(client, pid, [{"shoot_date": "2026-12-14", "cast_member_ids": [petr["id"]]}]).json()
    assert issue["status"] == "outside" and issue["agreed_days"] == ["2026-12-20"]
    history = client.get(url, headers=AUTH).json()
    assert sorted(h["id"] for h in history) == sorted([old["id"], new["id"]])
    assert next(h for h in history if h["id"] == old["id"])["withdrawn_at"]


def test_withdrawing_every_agreement_goes_back_to_not_entered(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    only = _agree(client, pid, petr, ["2026-12-14"])
    client.post(f"/api/v1/productions/{pid}/cast-members/{petr['id']}/agreements/{only['id']}/withdraw", headers=AUTH)
    [issue] = _check(client, pid, [{"shoot_date": "2026-12-14", "cast_member_ids": [petr["id"]]}]).json()
    assert issue["status"] == "not_entered"


def test_a_swap_checks_each_day_against_its_new_date(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    anna = _actor(client, pid, "Anna Geislerová", "MARTA")
    _agree(client, pid, petr, ["2026-12-14"])
    _agree(client, pid, anna, ["2026-12-14", "2026-12-15"])
    issues = _check(client, pid, [
        {"shoot_date": "2026-12-15", "cast_member_ids": [petr["id"]]},
        {"shoot_date": "2026-12-14", "cast_member_ids": [anna["id"]]},
    ]).json()
    assert [(i["name"], i["shoot_date"]) for i in issues] == [("Petr Novák", "2026-12-15")]


def test_another_productions_actor_is_refused_everywhere(client: TestClient) -> None:
    pid, other = _production(client), _production(client)
    stranger = _actor(client, other, "Someone", "ELSE")
    assert _check(client, pid, [{"shoot_date": "2026-12-14", "cast_member_ids": [stranger["id"]]}]).status_code == 422
    body = {"days": ["2026-12-14"], "agreed_by": "agent", "agreed_via": "email", "agreed_on": "2026-11-01"}
    assert client.post(f"/api/v1/productions/{pid}/cast-members/{stranger['id']}/agreements", json=body, headers=AUTH).status_code == 404
    assert client.get(f"/api/v1/productions/{pid}/cast-members/{stranger['id']}/agreements", headers=AUTH).status_code == 404
    mine = _actor(client, pid, "Petr Novák", "OTEC")
    theirs = _agree(client, other, stranger, ["2026-12-14"])
    assert client.post(f"/api/v1/productions/{pid}/cast-members/{mine['id']}/agreements/{theirs['id']}/withdraw", headers=AUTH).status_code == 404


def test_evidence_must_say_who_and_how(client: TestClient) -> None:
    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    url = f"/api/v1/productions/{pid}/cast-members/{petr['id']}/agreements"
    base = {"days": ["2026-12-14"], "agreed_by": "agent", "agreed_via": "email", "agreed_on": "2026-11-01"}
    assert client.post(url, json={**base, "days": []}, headers=AUTH).status_code == 422
    assert client.post(url, json={**base, "agreed_by": "somebody"}, headers=AUTH).status_code == 422
    assert client.post(url, json={**base, "agreed_via": "pigeon"}, headers=AUTH).status_code == 422


def test_removing_the_actor_removes_their_agreements(client: TestClient, db_session) -> None:
    from app.models.production import CastAgreement

    pid = _production(client)
    petr = _actor(client, pid, "Petr Novák", "OTEC")
    _agree(client, pid, petr, ["2026-12-14"])
    assert client.delete(f"/api/v1/productions/{pid}/cast-members/{petr['id']}", headers=AUTH).status_code == 204
    db_session.expire_all()
    assert db_session.query(CastAgreement).count() == 0

"""FR-140: an input-validation sweep over every POST/PATCH route under
`/api/v1`, so a request body missing a required field is actually rejected
(422) rather than silently accepted with a server-side default or `None`.
Reference: FR-134/FR-129's own systemic-sweep pattern (test_authz_sweep.py
isn't on `main` yet, still open PR #368 as of this writing, but shares the
same shape: check the whole mechanism once, not one spot-check).

Route discovery reads each route's own endpoint signature for a Pydantic
`BaseModel` parameter -- not a hand-maintained list -- so a new POST/PATCH
route with a JSON body is swept the moment it is added. A route with no
such parameter (a file upload, or a body-less action route like
`/call-sheets/{id}/cancel`) has no required field to validate and drops out
by construction, not by an allowlist.

Required fields -- including one level of nested `BaseModel` fields
(`PushSubscriptionCreate.keys`) -- are read straight from each model's own
`model_fields`, so a field that gains or loses a default changes what this
test checks without anyone updating it by hand.

`VALID_BODIES` is the one hand-maintained piece, by necessity: proving a
*missing* field is rejected needs a body that is otherwise valid, and
nothing but a human (or the route's own docs/tests) knows that a role must
be "viewer" or a department "AD" to pass validation and reach the handler.
It raises loudly for any swept model it doesn't recognise, rather than
skipping it, so a new model with required fields cannot go unswept quietly.
"""

import copy
import inspect
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import Enum, String

from app.main import app
from app.models.call_sheet import CallSheet, CallSheetRevision, CallSheetStatus, CastCallEntry, CrewCallEntry, ScheduleItem
from app.models.membership import ProductionMember
from app.models.production import CastMember, Contact, CrewMember, Location, Production
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate, CastCallEntryCreate, ConfirmRequest, CrewCallEntryCreate, MoveSceneRequest, RescheduleRequest, ScheduleItemCreate, SwapDaysRequest
from app.schemas.production import CastMemberCreate, CastMemberUpdate, ContactCreate, ContactUpdate, CrewMemberCreate, CrewMemberUpdate, LocationCreate, LocationUpdate, MemberCreate, ProductionCreate, ProductionUpdate
from app.schemas.push import PushSubscriptionCreate


def _api_routes():
    """Every route FastAPI serves, flattened out of its routers.

    Same shape as FR-134's own `_api_routes()` (test_authz_sweep.py, not yet
    on `main`): this FastAPI version (0.141) defers `include_router` into an
    `_IncludedRouter` wrapper instead of flattening `app.routes` eagerly, so
    a plain `for route in app.routes` only sees 5 opaque wrappers.
    """
    for route in app.routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from route.original_router.routes
        else:
            yield route


def _body_model(route) -> type[BaseModel] | None:
    """The Pydantic model a route's own endpoint signature declares as its
    JSON body, read straight off the function's parameter annotations.
    `None` for a route with no such parameter (a file upload via
    `UploadFile = File(...)`, or an action route that takes no body)."""
    for param in inspect.signature(route.endpoint).parameters.values():
        ann = param.annotation
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            return ann
    return None


def _required_field_paths(model: type[BaseModel], prefix: str = "") -> list[str]:
    """Dotted paths to every required field, recursing one level into a
    required field that is itself a `BaseModel` -- so `PushSubscriptionCreate`
    yields `keys`, `keys.p256dh`, and `keys.auth`, not just `keys`."""
    paths: list[str] = []
    for name, field in model.model_fields.items():
        path = f"{prefix}{name}"
        if not field.is_required():
            continue
        paths.append(path)
        ann = field.annotation
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            paths.extend(_required_field_paths(ann, prefix=f"{path}."))
    return paths


def _post_patch_body_routes() -> list[tuple[str, str, type[BaseModel]]]:
    found = []
    for route in _api_routes():
        model = _body_model(route)
        if model is None:
            continue
        path = getattr(route, "path", "") or ""
        for method in sorted(route.methods - {"HEAD"}):
            if method in ("POST", "PATCH"):
                found.append((method, path, model))
    return found


ROUTES = _post_patch_body_routes()
# The subset a "missing a required field" sweep can say anything about. A
# model with zero required fields -- every PATCH's own `*Update` schema, and
# `CallSheetRevisionCreate` (publishing a hot revision needs nothing but the
# call sheet it's published against) -- has no field to drop; that is this
# item's own scope boundary, asserted explicitly below rather than silently
# producing an empty parametrize list for those routes.
ROUTES_WITH_REQUIRED_FIELDS = [(m, p, model) for m, p, model in ROUTES if _required_field_paths(model)]
ROUTES_WITHOUT_REQUIRED_FIELDS = {(m, p) for m, p, model in ROUTES if not _required_field_paths(model)}


def test_route_discovery_found_the_expected_shape() -> None:
    """Canary on discovery: if it collapsed to nothing, every test below
    would sweep zero routes and pass vacuously."""
    assert len(ROUTES) >= 10, ROUTES
    assert len(ROUTES_WITH_REQUIRED_FIELDS) >= 7, ROUTES_WITH_REQUIRED_FIELDS
    # Every route with no required field is either a PATCH (every *Update
    # schema in this API makes every field optional by design) or the one
    # POST that behaves the same way (publishing a revision).
    unexpected = {(m, p) for m, p in ROUTES_WITHOUT_REQUIRED_FIELDS if m != "PATCH" and p != "/call-sheets/{call_sheet_id}/revisions"}
    assert not unexpected, unexpected


# A model that loses one required field out of several (e.g. `department`
# on `CrewMemberCreate`, which also requires `contact_id` and `position`)
# stays in `ROUTES_WITH_REQUIRED_FIELDS` either way -- only the one
# parametrize case for that field quietly disappears from
# `MISSING_FIELD_CASES`, with nothing left to fail. Pinning each model's
# expected required-field set here, independent of route discovery above,
# is what actually catches that: verified directly by temporarily making
# `CrewMemberCreate.department` optional (keeping `contact_id`/`position`
# required) -- the sweep's own route/field discovery stayed green and
# silently dropped one parametrize case; this check failed loudly, naming
# `CrewMemberCreate` and the missing `department`; reverted after.
EXPECTED_REQUIRED_FIELDS: dict[type[BaseModel], set[str]] = {
    ProductionCreate: {"name"},
    ContactCreate: {"name"},
    LocationCreate: {"name"},
    MemberCreate: {"email", "role"},
    CastMemberCreate: {"contact_id", "character_name"},
    CrewMemberCreate: {"contact_id", "department", "position"},
    CallSheetCreate: {"shoot_date", "day_number", "day_count", "initial_revision"},
    PushSubscriptionCreate: {"endpoint", "keys", "keys.p256dh", "keys.auth", "link_url"},
    ConfirmRequest: {"revision_letter"},
    MoveSceneRequest: {"scene_number", "target_call_sheet_id", "expected_revision_letter", "expected_target_revision_letter"},
    RescheduleRequest: {"shoot_date", "expected_revision_letter"},
    SwapDaysRequest: {"other_call_sheet_id", "expected_revision_letter", "expected_other_revision_letter"},
}


def test_every_swept_models_required_fields_match_the_pinned_expectation() -> None:
    swept_models = {model for _, _, model in ROUTES_WITH_REQUIRED_FIELDS}
    assert swept_models == set(EXPECTED_REQUIRED_FIELDS), swept_models ^ set(EXPECTED_REQUIRED_FIELDS)
    for model, expected in EXPECTED_REQUIRED_FIELDS.items():
        actual = set(_required_field_paths(model))
        assert actual == expected, f"{model.__name__}: expected required fields {expected}, found {actual}"


def _valid_body(model: type[BaseModel], ids: dict) -> dict:
    """A body for `model` that passes every required-field check -- the
    control every missing-field case below is diffed against. Needs real
    values a type annotation alone can't supply (a role string the handler
    accepts, a contact that actually exists), so it's a per-model mapping,
    not derived from the model like route discovery above."""
    if model is ProductionCreate:
        return {"name": "Sweep production"}
    if model is ContactCreate:
        return {"name": "Sweep contact"}
    if model is LocationCreate:
        return {"name": "Sweep location"}
    if model is MemberCreate:
        return {"email": "sweep-member@example.com", "role": "viewer"}
    if model is CastMemberCreate:
        return {"contact_id": ids["contact_id"], "character_name": "Extra"}
    if model is CrewMemberCreate:
        return {"contact_id": ids["contact_id"], "department": "AD", "position": "3rd AD"}
    if model is CallSheetCreate:
        return {"shoot_date": "2026-01-01", "day_number": 1, "day_count": 1, "initial_revision": {}}
    if model is PushSubscriptionCreate:
        return {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "p", "auth": "a"}, "link_url": "https://example.com/sheet"}
    if model is ConfirmRequest:
        return {"revision_letter": "A"}
    if model is MoveSceneRequest:
        return {"scene_number": "1", "target_call_sheet_id": ids["other_call_sheet_id"], "expected_revision_letter": "A", "expected_target_revision_letter": "A"}
    if model is RescheduleRequest:
        return {"shoot_date": "2030-01-01", "expected_revision_letter": "A"}
    if model is SwapDaysRequest:
        return {"other_call_sheet_id": ids["other_call_sheet_id"], "expected_revision_letter": "A", "expected_other_revision_letter": "A"}
    raise AssertionError(f"no VALID_BODIES example registered for {model.__name__}; add one so this sweep covers it")


def _without(body: dict, field_path: str) -> dict:
    """A deep copy of `body` with the value at a dotted path removed."""
    out = copy.deepcopy(body)
    *parents, leaf = field_path.split(".")
    node = out
    for part in parents:
        node = node[part]
    del node[leaf]
    return out


def _fill(path: str, ids: dict) -> str:
    """Substitute `{production_id}`/`{token}` with real ones (the handlers
    that own this item's routes read them before touching the body); any
    other path param gets a random UUID."""
    parts = []
    for segment in path.split("/"):
        if segment == "{production_id}":
            parts.append(ids["production_id"])
        elif segment == "{token}":
            parts.append(ids["crew_member_token"])
        elif segment == "{call_sheet_id}":
            parts.append(ids["call_sheet_id"])
        elif segment.startswith("{") and segment.endswith("}"):
            parts.append(str(uuid.uuid4()))
        else:
            parts.append(segment)
    return "/".join(parts)


@pytest.fixture()
def _ids(client: TestClient, auth_headers) -> dict:
    """Real ids to fill into a route's path or FK fields. The service token
    (`auth_headers`) owns every production (`app/authz.py` resolves it to
    `ProductionRole.OWNER` on any production id), so this sweep is pure body
    validation, not a second authz check -- FR-134 already owns that one."""
    pid = client.post("/api/v1/productions", json={"name": "Validation sweep"}, headers=auth_headers).json()["id"]
    contact_id = client.post("/api/v1/contacts", json={"name": "Validation sweep contact"}, headers=auth_headers).json()["id"]
    crew = client.post(
        f"/api/v1/productions/{pid}/crew-members",
        json={"contact_id": contact_id, "department": "AD", "position": "2nd AD"},
        headers=auth_headers,
    ).json()
    sheet = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-01-01", "day_number": 1, "day_count": 2, "initial_revision": {
            "schedule_items": [{"order_index": 1, "scene_number": "1", "int_ext": "INT", "day_night": "DAY", "set_description": "Set", "page_count_eighths": 8}],
        }},
        headers=auth_headers,
    ).json()
    other = client.post(
        f"/api/v1/productions/{pid}/call-sheets",
        json={"shoot_date": "2026-01-02", "day_number": 2, "day_count": 2, "initial_revision": {}},
        headers=auth_headers,
    ).json()
    return {"production_id": pid, "contact_id": contact_id, "crew_member_token": crew["personal_token"], "call_sheet_id": sheet["id"], "other_call_sheet_id": other["id"]}


@pytest.mark.parametrize("method,path,model", ROUTES_WITH_REQUIRED_FIELDS, ids=[f"{m}:{p}" for m, p, _ in ROUTES_WITH_REQUIRED_FIELDS])
def test_the_full_valid_body_is_accepted(client: TestClient, auth_headers, _ids, method, path, model) -> None:
    """Canary for the sweep below: proves each route's own entry in
    `_valid_body` really is valid, so a 422 in the next test is caused by
    the field that was dropped, not by a stale fixture."""
    url = "/api/v1" + _fill(path, _ids)
    resp = client.request(method, url, headers=auth_headers, json=_valid_body(model, _ids))
    assert resp.status_code < 300, f"{method} {path}: the control (fully valid) body was rejected: {resp.status_code} {resp.text}"


MISSING_FIELD_CASES = [(m, p, model, field) for m, p, model in ROUTES_WITH_REQUIRED_FIELDS for field in _required_field_paths(model)]


@pytest.mark.parametrize(
    "method,path,model,field_path",
    MISSING_FIELD_CASES,
    ids=[f"{m}:{p}:{fp}" for m, p, _, fp in MISSING_FIELD_CASES],
)
def test_a_missing_required_field_is_rejected(client: TestClient, auth_headers, _ids, method, path, model, field_path) -> None:
    url = "/api/v1" + _fill(path, _ids)
    body = _without(_valid_body(model, _ids), field_path)
    resp = client.request(method, url, headers=auth_headers, json=body)
    assert resp.status_code == 422, f"{method} {path} accepted a body missing required field {field_path!r}: {resp.status_code} {resp.text}"


# --- FR-222: what the fields accept, not only whether they are present. ------------------

TABLE_OF = {"": CallSheet, "initial_revision.": CallSheetRevision, "initial_revision.schedule_items.0.": ScheduleItem,
            "initial_revision.crew_calls.0.": CrewCallEntry, "initial_revision.cast_calls.0.": CastCallEntry}
MODEL_OF = {"": CallSheetCreate, "initial_revision.": CallSheetRevisionCreate, "initial_revision.schedule_items.0.": ScheduleItemCreate,
            "initial_revision.crew_calls.0.": CrewCallEntryCreate, "initial_revision.cast_calls.0.": CastCallEntryCreate}


def _stored_text_fields() -> list[tuple[str, int]]:
    """Every field of the create payload stored in a String column, read from the models themselves
    so a new text field is swept the moment it is added."""
    found = []
    for prefix, model in MODEL_OF.items():
        columns = TABLE_OF[prefix].__table__.columns
        for name in model.model_fields:
            column = columns.get(name)
            if column is not None and isinstance(column.type, String) and not isinstance(column.type, Enum) and column.type.length:
                found.append((f"{prefix}{name}", column.type.length))
    return found


TEXT_FIELDS = _stored_text_fields()
TIME_FIELDS = [path for path, _ in TEXT_FIELDS if path.endswith(("_time", "_call", "sunrise", "sunset"))]


def test_the_field_walk_found_what_it_should() -> None:
    assert {"unit_name", "initial_revision.safety_notes", "initial_revision.schedule_items.0.scene_number", "initial_revision.crew_calls.0.note"} <= {p for p, _ in TEXT_FIELDS}
    assert set(TIME_FIELDS) == {
        "initial_revision.general_crew_call", "initial_revision.shooting_call", "initial_revision.sunrise", "initial_revision.sunset",
        "initial_revision.crew_calls.0.call_time", "initial_revision.crew_calls.0.pickup_time",
        "initial_revision.cast_calls.0.pickup_time", "initial_revision.cast_calls.0.call_time", "initial_revision.cast_calls.0.makeup_hair_time", "initial_revision.cast_calls.0.on_set_time",
    }


@pytest.fixture()
def _full_day(client: TestClient, auth_headers, _ids) -> tuple[str, dict]:
    """The create route and a body touching every nested list, shaped as the editor sends it."""
    contact = client.post("/api/v1/contacts", json={"name": "Actor"}, headers=auth_headers).json()["id"]
    actor = client.post(f"/api/v1/productions/{_ids['production_id']}/cast-members", json={"contact_id": contact, "character_name": "Hero"}, headers=auth_headers).json()
    crew = client.get(f"/api/v1/productions/{_ids['production_id']}/crew-members", headers=auth_headers).json()[0]
    body = {
        "shoot_date": "2031-03-03", "day_number": 3, "day_count": 3, "unit_name": "Main Unit",
        "initial_revision": {
            "general_crew_call": "06:30", "shooting_call": "07:30", "sunrise": "06:41", "sunset": "19:03", "weather_forecast": "Clear", "safety_notes": "Mind the river", "created_by": "editor",
            "head_of_day_crew_member_id": None,
            "schedule_items": [{"order_index": 1, "scene_number": "42A", "int_ext": "EXT", "day_night": "DAY", "set_description": "River", "location_id": None, "page_count_eighths": 19}],
            "crew_calls": [{"crew_member_id": crew["id"], "call_time": "05:45", "pickup_time": "05:00", "note": "Pre-rig"}],
            "cast_calls": [{"cast_member_id": actor["id"], "status_code": "W", "pickup_time": "05:15", "call_time": "06:00", "makeup_hair_time": "06:15", "on_set_time": "08:00"}],
        },
    }
    return f"/api/v1/productions/{_ids['production_id']}/call-sheets", body


def _with(body: dict, path: str, value) -> dict:
    out = copy.deepcopy(body)
    *parents, leaf = path.split(".")
    node = out
    for part in parents:
        node = node[int(part)] if part.isdigit() else node[part]
    node[leaf] = value
    return out


def _read(body: dict, path: str):
    node = body
    for part in path.split("."):
        node = node[int(part)] if part.isdigit() else node[part]
    return node


def test_the_day_body_is_valid_as_written(client: TestClient, auth_headers, _full_day) -> None:
    url, body = _full_day
    assert client.post(url, json=body, headers=auth_headers).status_code == 201


@pytest.mark.parametrize("path,length", TEXT_FIELDS, ids=[p for p, _ in TEXT_FIELDS])
def test_text_over_its_column_is_a_422_not_a_500(client: TestClient, auth_headers, _full_day, path, length) -> None:
    url, body = _full_day
    assert client.post(url, json=_with(body, path, "x" * (length + 1)), headers=auth_headers).status_code == 422


@pytest.mark.parametrize("path,length", [(p, n) for p, n in TEXT_FIELDS if p not in TIME_FIELDS and not p.endswith("created_by")], ids=[p for p, _ in TEXT_FIELDS if p not in TIME_FIELDS and not p.endswith("created_by")])
def test_text_exactly_at_its_column_is_stored(client: TestClient, auth_headers, _full_day, path, length) -> None:
    url, body = _full_day
    r = client.post(url, json=_with(body, path, "x" * length), headers=auth_headers)
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("path", [p for p, _ in TEXT_FIELDS], ids=[p for p, _ in TEXT_FIELDS])
def test_a_nul_byte_is_a_422_not_a_500(client: TestClient, auth_headers, _full_day, path) -> None:
    url, body = _full_day
    assert client.post(url, json=_with(body, path, "a\x00b"), headers=auth_headers).status_code == 422


def test_created_by_leaves_room_for_the_service_prefix(client: TestClient, auth_headers, _full_day) -> None:
    """The audit label is "service:" plus this value, in a String(255) column."""
    url, body = _full_day
    assert client.post(url, json=_with(body, "initial_revision.created_by", "x" * 247), headers=auth_headers).status_code == 201
    assert client.post(url, json=_with(_with(body, "initial_revision.created_by", "x" * 248), "day_number", 4), headers=auth_headers).status_code == 422


@pytest.mark.parametrize("path", TIME_FIELDS)
@pytest.mark.parametrize("value", ["25:99", "abc", "24:00", "24,00", "12:60", "6", "06:3", "06:30:00", "٠٦:٣٠", "06:30 pm", "TBD", "6;30"])
def test_something_that_is_not_a_time_is_refused(client: TestClient, auth_headers, _full_day, path, value) -> None:
    url, body = _full_day
    r = client.post(url, json=_with(body, path, value), headers=auth_headers)
    assert r.status_code == 422, f"{path}={value!r}: {r.status_code}"


@pytest.mark.parametrize("value,stored", [("00:00", "00:00"), ("23:59", "23:59"), ("06:30", "06:30"), ("6:30", "06:30"), ("6.30", "06:30"), ("6,30", "06:30"), ("06,30", "06:30"), (" 06:30 ", "06:30"), ("", None), ("  ", None), (None, None)])
def test_what_people_actually_type_as_a_time_is_kept(client: TestClient, auth_headers, _full_day, value, stored) -> None:
    url, body = _full_day
    r = client.post(url, json=_with(_with(body, "initial_revision.shooting_call", value), "initial_revision.crew_calls.0.pickup_time", value), headers=auth_headers)
    assert r.status_code == 201, r.text
    revision = r.json()["current_revision"]
    assert revision["shooting_call"] == stored and revision["crew_calls"][0]["pickup_time"] == stored


@pytest.mark.parametrize("path,value", [
    ("initial_revision.schedule_items.0.page_count_eighths", -1),
    ("initial_revision.schedule_items.0.page_count_eighths", 8001),
    ("initial_revision.schedule_items.0.page_count_eighths", 2**31),
    ("initial_revision.schedule_items.0.order_index", -1),
    ("initial_revision.schedule_items.0.order_index", 2**31),
    ("day_number", 2**31),
    ("day_count", 2**31),
])
def test_numbers_no_shoot_needs_are_refused_before_they_overflow_a_column(client: TestClient, auth_headers, _full_day, path, value) -> None:
    url, body = _full_day
    assert client.post(url, json=_with(body, path, value), headers=auth_headers).status_code == 422


@pytest.mark.parametrize("path,value", [("initial_revision.schedule_items.0.page_count_eighths", 8000), ("initial_revision.schedule_items.0.page_count_eighths", 0), ("initial_revision.schedule_items.0.order_index", 0)])
def test_the_bounds_themselves_are_allowed(client: TestClient, auth_headers, _full_day, path, value) -> None:
    url, body = _full_day
    assert client.post(url, json=_with(body, path, value), headers=auth_headers).status_code == 201


def test_a_person_named_twice_in_the_crew_calls_is_a_422_not_a_500(client: TestClient, auth_headers, _full_day, _ids) -> None:
    url, body = _full_day
    entry = _read(body, "initial_revision.crew_calls.0")
    r = client.post(url, json=_with(body, "initial_revision.crew_calls", [entry, {**entry, "call_time": "09:00"}]), headers=auth_headers)
    assert r.status_code == 422 and "more than once" in r.text
    r = client.post(f"/api/v1/call-sheets/{_ids['call_sheet_id']}/revisions", json={"crew_calls": [entry, entry]}, headers=auth_headers)
    assert r.status_code == 422 and "more than once" in r.text


def test_publishing_a_revision_is_validated_like_creating_a_day(client: TestClient, auth_headers, _ids) -> None:
    url = f"/api/v1/call-sheets/{_ids['call_sheet_id']}/revisions"
    assert client.post(url, json={"general_crew_call": "25:99"}, headers=auth_headers).status_code == 422
    assert client.post(url, json={"safety_notes": "x" * 2001}, headers=auth_headers).status_code == 422
    assert client.post(url, json={"general_crew_call": "07:00"}, headers=auth_headers).status_code == 201


def test_actual_times_are_validated_on_the_way_in(client: TestClient, auth_headers, _ids) -> None:
    url = f"/api/v1/call-sheets/{_ids['call_sheet_id']}/actuals"
    assert client.put(url, json={"first_shot": "25:99"}, headers=auth_headers).status_code == 422
    assert client.put(url, json={"note": "x" * 501}, headers=auth_headers).status_code == 422
    assert client.put(url, json={"wrap": "a\x00"}, headers=auth_headers).status_code == 422
    assert client.put(url, json={"first_shot": "7:05", "note": "ok"}, headers=auth_headers).json()["actuals"]["first_shot"] == "07:05"


def test_standing_times_are_validated_on_the_way_in(client: TestClient, auth_headers, _ids) -> None:
    pid, contact = _ids["production_id"], _ids["contact_id"]
    assert client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "AD", "position": "x", "standard_call_time": "abc"}, headers=auth_headers).status_code == 422
    assert client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact, "character_name": "x", "standard_pickup_time": "25:99"}, headers=auth_headers).status_code == 422
    crew = client.get(f"/api/v1/productions/{pid}/crew-members", headers=auth_headers).json()[0]
    assert client.patch(f"/api/v1/productions/{pid}/crew-members/{crew['id']}", json={"standard_call_time": "abc"}, headers=auth_headers).status_code == 422
    assert client.patch(f"/api/v1/productions/{pid}/crew-members/{crew['id']}", json={"standard_call_time": "6:30"}, headers=auth_headers).json()["standard_call_time"] == "06:30"


def _legacy_day(db_session, client: TestClient, auth_headers) -> tuple[str, str, str]:
    """A day holding values today's validation would refuse, written straight to the tables, as old data was."""
    pid = client.post("/api/v1/productions", json={"name": "Legacy"}, headers=auth_headers).json()["id"]
    contact = client.post("/api/v1/contacts", json={"name": "Old timer"}, headers=auth_headers).json()["id"]
    crew = client.post(f"/api/v1/productions/{pid}/crew-members", json={"contact_id": contact, "department": "AD", "position": "x"}, headers=auth_headers).json()
    actor = client.post(f"/api/v1/productions/{pid}/cast-members", json={"contact_id": contact, "character_name": "Hero"}, headers=auth_headers).json()
    db_session.query(CrewMember).filter(CrewMember.id == crew["id"]).update({"standard_call_time": "brzy"})
    db_session.query(CastMember).filter(CastMember.id == actor["id"]).update({"standard_pickup_time": "25:99"})
    sheet = CallSheet(production_id=pid, shoot_date=date(2031, 5, 5), day_number=1, day_count=1, status=CallSheetStatus.PUBLISHED, actual_first_shot="abc")
    db_session.add(sheet)
    db_session.flush()
    revision = CallSheetRevision(call_sheet_id=sheet.id, revision_letter="A", is_current=True, general_crew_call="25:99", shooting_call="abc", sunrise="6h", sunset="later", shoot_date=sheet.shoot_date)
    db_session.add(revision)
    db_session.flush()
    db_session.add(ScheduleItem(revision_id=revision.id, order_index=-1, scene_number="1", int_ext="INT", day_night="DAY", set_description="Set", page_count_eighths=99999))
    db_session.add(CrewCallEntry(revision_id=revision.id, crew_member_id=crew["id"], call_time="abc", pickup_time="99:99", note="x"))
    db_session.add(CastCallEntry(revision_id=revision.id, cast_member_id=actor["id"], status_code="W", pickup_time="abc", call_time="abc", makeup_hair_time="abc", on_set_time="abc"))
    db_session.commit()
    return pid, str(sheet.id), crew["personal_token"]


def test_stored_values_from_before_the_validation_still_read_back(client: TestClient, auth_headers, db_session) -> None:
    pid, sheet_id, token = _legacy_day(db_session, client, auth_headers)
    for url, headers in ((f"/api/v1/call-sheets/{sheet_id}", auth_headers), (f"/api/v1/public/call-sheets/{sheet_id}", {}),
                         (f"/api/v1/productions/{pid}/call-sheets", auth_headers), (f"/api/v1/public/call-sheets/{sheet_id}/me/{token}", {}),
                         (f"/api/v1/call-sheets/{sheet_id}/history", auth_headers), (f"/api/v1/public/crew/{token}/next", {}),
                         (f"/api/v1/productions/{pid}/crew-members", auth_headers), (f"/api/v1/productions/{pid}/cast-members", auth_headers)):
        r = client.get(url, headers=headers)
        assert r.status_code == 200, f"{url}: {r.status_code} {r.text}"
    assert client.get(f"/api/v1/call-sheets/{sheet_id}", headers=auth_headers).json()["current_revision"]["general_crew_call"] == "25:99"


def test_old_values_are_carried_forward_rather_than_blocking_a_change_that_does_not_touch_them(client: TestClient, auth_headers, db_session) -> None:
    """Copying a revision forward, and moving a day, rebuild a payload from stored rows: that is not new input."""
    _, sheet_id, _ = _legacy_day(db_session, client, auth_headers)
    r = client.post(f"/api/v1/call-sheets/{sheet_id}/revisions", json={"general_crew_call": "07:00"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["crew_calls"][0]["call_time"] == "abc" and r.json()["cast_calls"][0]["pickup_time"] == "abc"
    r = client.post(f"/api/v1/call-sheets/{sheet_id}/reschedule", json={"shoot_date": "2031-05-06", "expected_revision_letter": "B"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["current_revision"]["crew_calls"][0]["call_time"] == "abc"


# --- FR-222 review: the same limits on the production, contact, location, crew and cast bodies. ---

STORED_IN = {
    ContactCreate: Contact, ContactUpdate: Contact, ProductionCreate: Production, ProductionUpdate: Production,
    LocationCreate: Location, LocationUpdate: Location, CrewMemberCreate: CrewMember, CrewMemberUpdate: CrewMember,
    CastMemberCreate: CastMember, CastMemberUpdate: CastMember, MemberCreate: ProductionMember,
}


def _other_text_cases() -> list[tuple[str, str, type[BaseModel], str, int]]:
    """Every swept route whose body model is stored in one of these tables, with each String column it writes."""
    cases = []
    for method, path, model in ROUTES:
        table = STORED_IN.get(model)
        if table is None:
            continue
        columns = table.__table__.columns
        for name in model.model_fields:
            column = columns.get(name)
            if column is not None and isinstance(column.type, String) and not isinstance(column.type, Enum) and column.type.length:
                cases.append((method, path, model, name, column.type.length))
    return cases


OTHER_TEXT_CASES = _other_text_cases()


def test_the_other_walk_found_what_it_should() -> None:
    found = {(model.__name__, name) for _, _, model, name, _ in OTHER_TEXT_CASES}
    assert {("ContactCreate", "name"), ("ContactUpdate", "phone"), ("ProductionCreate", "name"), ("LocationUpdate", "address"),
            ("CrewMemberCreate", "department"), ("CastMemberCreate", "character_name"), ("MemberCreate", "email")} <= found
    assert set(STORED_IN) <= {model for _, _, model in ROUTES}


@pytest.mark.parametrize("method,path,model,name,length", OTHER_TEXT_CASES, ids=[f"{m}:{p}:{n}" for m, p, _, n, _ in OTHER_TEXT_CASES])
def test_other_bodies_refuse_over_length_text_and_nul_bytes_with_a_422(client: TestClient, auth_headers, _ids, method, path, model, name, length) -> None:
    url = "/api/v1" + _fill(path, _ids)
    base = _valid_body(model, _ids) if method == "POST" else {}
    for value in ("x" * (length + 1), "a\x00b"):
        r = client.request(method, url, headers=auth_headers, json={**base, name: value})
        assert r.status_code == 422, f"{method} {path} {name}={value[:5]!r}: {r.status_code} {r.text[:200]}"

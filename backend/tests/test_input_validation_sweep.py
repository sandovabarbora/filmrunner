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

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import app
from app.schemas.call_sheet import CallSheetCreate, ConfirmRequest, MoveSceneRequest, RescheduleRequest, SwapDaysRequest
from app.schemas.production import CastMemberCreate, ContactCreate, CrewMemberCreate, LocationCreate, MemberCreate, ProductionCreate
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

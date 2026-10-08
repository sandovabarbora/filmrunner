"""FR-134: a comprehensive authz sweep over every permission-gated
production route, so a route that silently loses its permission check
fails CI instead of shipping. Reference: app/authz.py, ADR-005.

Two different discovery mechanisms, deliberately:

- `SCOPED_ROUTES` finds every route by *module and path* (every endpoint
  defined in `app.routers.productions` whose path needs a production or a
  contact to belong to someone, minus `ALLOWLIST`'s intentionally open
  routes). This is what `test_stranger_is_refused_on_every_scoped_route`
  sweeps — because it doesn't look for a permission check to exist, a route
  that loses its `Depends(require(...))` (or its `_require_contact_edit`
  call) stays in the sweep and the test fails loudly instead of the route
  quietly dropping out of a check that only finds what's still there.
- `GATED_ROUTES` finds the subset of those that currently declare
  `Depends(require(...))`, read from the dependency's own closure cells,
  used only to know *which* permission a route needs for the stricter
  viewer-must-be-refused assertion below.
"""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.authz import CREW_EDIT, DAY_PUBLISH, PRODUCTION_MANAGE_MEMBERS
from app.main import app

# These three gate the actions BRIEF.md's "connect first" crew/day flows
# depend on; FR-134's own dod names them as the set a viewer must never pass.
RESTRICTED_PERMISSIONS = {CREW_EDIT, DAY_PUBLISH, PRODUCTION_MANAGE_MEMBERS}

# Routes on app.routers.productions that are deliberately not scoped to a
# production or a contact the caller already has standing on: creating a
# production or a loose contact needs no prior standing, listing productions
# is self-filtered by membership (visible_productions), the contacts search
# is a global lookup, and the public photo endpoint is unauthenticated by
# design (the crew's phones load it straight from a published sheet).
ALLOWLIST = {
    ("POST", "/productions"),
    ("GET", "/productions"),
    ("GET", "/contacts"),
    ("POST", "/contacts"),
    ("GET", "/public/contacts/{contact_id}/photo"),
}


def _api_routes():
    """Every route FastAPI serves, flattened out of its routers.

    This FastAPI version (0.141) defers `include_router` into an
    `_IncludedRouter` wrapper instead of flattening `app.routes` eagerly,
    so a plain `for route in app.routes` only sees 5 opaque wrappers plus
    the handful of routes declared directly on `app`.
    """
    for route in app.routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from route.original_router.routes
        else:
            yield route


def _required_permission(route) -> str | None:
    """The permission string a route's `Depends(require(...))` sub-dependency
    closes over, read directly from that function's closure cells (see
    `app.authz.require`, which returns a fresh `dependency` closing over
    `permission`)."""
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return None
    for dep in dependant.dependencies:
        call = dep.call
        if getattr(call, "__name__", None) != "dependency" or not call.__closure__:
            continue
        values = dict(zip(call.__code__.co_freevars, (cell.cell_contents for cell in call.__closure__)))
        if "permission" in values:
            return values["permission"]
    return None


def _scoped_routes() -> list[tuple[str, str]]:
    found = []
    for route in _api_routes():
        if getattr(getattr(route, "endpoint", None), "__module__", None) != "app.routers.productions":
            continue
        path = getattr(route, "path", "") or ""
        for method in sorted(route.methods - {"HEAD"}):
            if (method, path) in ALLOWLIST:
                continue
            found.append((method, path))
    return found


def _gated_production_routes() -> list[tuple[str, str, str]]:
    """(method, path, permission) for every `/productions...` route gated by
    `Depends(require(...))`. Excludes `/call-sheets` routes, which check
    permissions via `require_on(...)` inside the handler body, not as a
    FastAPI dependency the closure trick above can see, and excludes the
    contact-photo routes for the same reason (`_require_contact_edit`) —
    both out of this item's scope per its own dod wording ("a `require(...)`
    dependency"). The photo routes get their own explicit test below.
    """
    found = []
    for route in _api_routes():
        path = getattr(route, "path", "") or ""
        if not path.startswith("/productions"):
            continue
        permission = _required_permission(route)
        if permission is None:
            continue
        for method in sorted(route.methods - {"HEAD"}):
            found.append((method, path, permission))
    return found


SCOPED_ROUTES = _scoped_routes()
GATED_ROUTES = _gated_production_routes()


@pytest.fixture()
def users(monkeypatch: pytest.MonkeyPatch):
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()

    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token: str):
            class Key:
                key = public

            return Key()

    monkeypatch.setattr(auth, "_jwk_client", lambda: FakeJwkClient())

    def headers(email: str) -> dict[str, str]:
        now = int(time.time())
        token = jwt.encode(
            {"sub": f"uid-{email}", "email": email, "aud": "authenticated", "iat": now, "exp": now + 600},
            private,
            algorithm="ES256",
        )
        return {"Authorization": f"Bearer {token}"}

    return headers


def _fill(path: str, production_id: str, contact_id: str) -> str:
    """Substitute `{production_id}`/`{contact_id}` with real ones and any
    other path param with a random UUID.

    A real id is needed only where the authz check itself reads it
    (`require(...)` reads `production_id`; `_require_contact_edit` reads
    `contact_id`); every other id (location_id, member_id, ...) can stay
    random because a permission refusal is raised while FastAPI is still
    resolving dependencies, before a handler would get far enough to look
    one up and 404 on it instead — confirmed empirically for every route
    this test sweeps."""
    parts = []
    for segment in path.split("/"):
        if segment == "{production_id}":
            parts.append(production_id)
        elif segment == "{contact_id}":
            parts.append(contact_id)
        elif segment.startswith("{") and segment.endswith("}"):
            parts.append(str(uuid.uuid4()))
        else:
            parts.append(segment)
    return "/".join(parts)


def test_route_discovery_found_the_expected_shape() -> None:
    """Canary on both discovery mechanisms: if either collapses, the tests
    below would pass by sweeping nothing."""
    assert len(SCOPED_ROUTES) >= 20, SCOPED_ROUTES
    assert len(GATED_ROUTES) >= 20, GATED_ROUTES
    permissions_seen = {permission for _, _, permission in GATED_ROUTES}
    assert CREW_EDIT in permissions_seen
    assert PRODUCTION_MANAGE_MEMBERS in permissions_seen


@pytest.fixture()
def _production_and_contact(client: TestClient, users):
    """An owner's production, with a contact in its crew, to fill real ids
    into a route path; a stranger who belongs to neither."""
    owner = users("sweep-owner@example.com")
    stranger = users("sweep-stranger@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Sweep"}, headers=owner).json()["id"]
    cid = client.post("/api/v1/contacts", json={"name": "Sweep Contact"}, headers=owner).json()["id"]
    client.post(
        f"/api/v1/productions/{pid}/crew-members",
        json={"contact_id": cid, "department": "AD", "position": "2nd AD"},
        headers=owner,
    )
    return owner, stranger, pid, cid


def _request(client: TestClient, method: str, url: str, path: str, headers: dict[str, str]):
    """Most routes just need *some* body to get past pydantic and into the
    authz check; the photo upload needs an actual file part, since its
    `_require_contact_edit` call runs inside the handler body, after
    FastAPI's own required-field validation — not as a `Depends` sub-
    dependency that would run (and could refuse) first."""
    if method == "POST" and path.endswith("/photo"):
        return client.post(url, headers=headers, files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")})
    return client.request(method, url, headers=headers, json=({} if method in ("POST", "PATCH") else None))


@pytest.mark.parametrize("method,path", SCOPED_ROUTES, ids=[f"{m}:{p}" for m, p in SCOPED_ROUTES])
def test_stranger_is_refused_on_every_scoped_route(client: TestClient, _production_and_contact, method: str, path: str) -> None:
    _owner, stranger, pid, cid = _production_and_contact
    url = "/api/v1" + _fill(path, pid, cid)
    resp = _request(client, method, url, path, stranger)
    assert resp.status_code == 403, f"{method} {path} let a non-member stranger through: {resp.status_code} {resp.text}"


@pytest.mark.parametrize(
    "method,path,permission",
    [(m, p, perm) for m, p, perm in GATED_ROUTES if perm in RESTRICTED_PERMISSIONS],
    ids=[f"{m}:{p}" for m, p, perm in GATED_ROUTES if perm in RESTRICTED_PERMISSIONS],
)
def test_viewer_is_refused_on_restricted_routes(client: TestClient, users, method: str, path: str, permission: str) -> None:
    owner = users("sweep-owner2@example.com")
    viewer = users("sweep-viewer@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Sweep"}, headers=owner).json()["id"]
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "sweep-viewer@example.com", "role": "viewer"}, headers=owner)
    url = "/api/v1" + _fill(path, pid, str(uuid.uuid4()))
    resp = client.request(method, url, headers=viewer, json=({} if method in ("POST", "PATCH") else None))
    assert resp.status_code == 403, f"{method} {path} (permission={permission}) let a viewer through: {resp.status_code} {resp.text}"


def test_viewer_cannot_edit_crew_via_the_contact_photo_routes(client: TestClient, users) -> None:
    """`/contacts/{id}/photo` isn't `Depends(require(...))`-gated like the
    routes above — it funnels through `_require_contact_edit`
    (routers/productions.py), which checks `CREW_EDIT` across every
    production that has this contact in its crew. Checked explicitly per
    this item's own dod, in addition to the generic stranger sweep above
    (which already covers both photo routes via `SCOPED_ROUTES`)."""
    owner = users("sweep-photo-owner@example.com")
    viewer = users("sweep-photo-viewer@example.com")
    pid = client.post("/api/v1/productions", json={"name": "Photo sweep"}, headers=owner).json()["id"]
    client.post(f"/api/v1/productions/{pid}/members", json={"email": "sweep-photo-viewer@example.com", "role": "viewer"}, headers=owner)
    cid = client.post("/api/v1/contacts", json={"name": "Sweep Contact"}, headers=owner).json()["id"]
    client.post(
        f"/api/v1/productions/{pid}/crew-members",
        json={"contact_id": cid, "department": "AD", "position": "2nd AD"},
        headers=owner,
    )

    resp = client.post(f"/api/v1/contacts/{cid}/photo", files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")}, headers=viewer)
    assert resp.status_code == 403, f"POST /contacts/{{id}}/photo let a viewer through: {resp.status_code} {resp.text}"
    resp = client.delete(f"/api/v1/contacts/{cid}/photo", headers=viewer)
    assert resp.status_code == 403, f"DELETE /contacts/{{id}}/photo let a viewer through: {resp.status_code} {resp.text}"

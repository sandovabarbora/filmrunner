"""Policy-based access to productions: roles map to explicit permissions,
and every production-scoped endpoint asks for exactly the permission it
needs (least privilege). Reference: docs/adr/ADR-005-roles.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import Principal, require_principal
from app.database import get_db
from app.models.membership import ProductionMember, ProductionRole
from app.models.production import Production

# Permissions are strings so they read the same in the API and the editor.
PRODUCTION_READ = "production:read"
PRODUCTION_MANAGE_MEMBERS = "production:manage_members"
PRODUCTION_EDIT = "production:edit"  # name and lifecycle status (FR-34)
DAY_PUBLISH = "day:publish"
CREW_EDIT = "crew:edit"

ROLE_PERMISSIONS: dict[ProductionRole, frozenset[str]] = {
    ProductionRole.OWNER: frozenset({PRODUCTION_READ, PRODUCTION_MANAGE_MEMBERS, PRODUCTION_EDIT, DAY_PUBLISH, CREW_EDIT}),
    ProductionRole.EDITOR: frozenset({PRODUCTION_READ, PRODUCTION_EDIT, DAY_PUBLISH, CREW_EDIT}),
    ProductionRole.VIEWER: frozenset({PRODUCTION_READ}),
}


@dataclass(frozen=True)
class Access:
    """The caller's standing on one production."""

    principal: Principal
    production: Production
    role: ProductionRole
    permissions: frozenset[str]


def membership_for(db: Session, principal: Principal, production_id: uuid.UUID) -> ProductionMember | None:
    """Find the caller's membership; bind the Supabase user id on first sight."""
    if principal.kind != "user":
        return None
    query = db.query(ProductionMember).filter(ProductionMember.production_id == production_id)
    member = query.filter(ProductionMember.user_id == principal.subject).first()
    if member is None and principal.email:
        member = query.filter(ProductionMember.email == principal.email.lower()).first()
        if member is not None and member.user_id is None:
            member.user_id = principal.subject
            db.commit()
    return member


def resolve_access(db: Session, principal: Principal, production_id: uuid.UUID) -> Access:
    """Raise 404 for an unknown production, 403 for a non-member."""
    production = db.get(Production, production_id)
    if production is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production not found")
    if principal.kind == "service":
        role = ProductionRole.OWNER
    else:
        member = membership_for(db, principal, production_id)
        if member is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No access to production {production.name}")
        role = member.role
    return Access(principal=principal, production=production, role=role, permissions=ROLE_PERMISSIONS[role])


def resolve_access_or_none(db: Session, principal: Principal, production_id: uuid.UUID) -> frozenset[str]:
    """Permissions on a production, or an empty set when the caller is not a member (no exception)."""
    try:
        return resolve_access(db, principal, production_id).permissions
    except HTTPException:
        return frozenset()


def require(permission: str):
    """Dependency factory: `access: Access = Depends(require(DAY_PUBLISH))`.

    The production id comes from the path parameter `production_id`.
    """

    def dependency(
        production_id: uuid.UUID,
        db: Session = Depends(get_db),
        principal: Principal = Depends(require_principal),
    ) -> Access:
        access = resolve_access(db, principal, production_id)
        if permission not in access.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Your role ({access.role.value}) cannot do this on {access.production.name}")
        return access

    return dependency


def require_on(db: Session, principal: Principal, production_id: uuid.UUID, permission: str) -> Access:
    """Same check for endpoints whose path carries a call-sheet id, not a production id."""
    access = resolve_access(db, principal, production_id)
    if permission not in access.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Your role ({access.role.value}) cannot do this on {access.production.name}")
    return access


def visible_productions(db: Session, principal: Principal) -> list[Production]:
    if principal.kind == "service":
        return list(db.query(Production).order_by(Production.created_at.desc()).all())
    ids = [
        m.production_id
        for m in db.query(ProductionMember).filter(
            (ProductionMember.user_id == principal.subject)
            | (ProductionMember.email == (principal.email or "").lower())
        )
    ]
    if not ids:
        return []
    return list(db.query(Production).filter(Production.id.in_(ids)).order_by(Production.created_at.desc()).all())

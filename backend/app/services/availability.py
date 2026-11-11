"""FR-228: is an actor called on a day they agreed to?

Only a warning: nothing here blocks a publish or proposes another plan.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.production import CastAgreement, CastMember
from app.schemas.production import AvailabilityCheck, AvailabilityIssue


class CastNotOnProduction(ValueError):
    """A check names someone who is not in this production's cast."""


def agreed_days(db: Session, cast_member_ids: set[uuid.UUID]) -> dict[uuid.UUID, set[date]]:
    """Agreed days per actor, from agreements still in force. An actor with none is absent from the result."""
    rows = db.query(CastAgreement).filter(CastAgreement.cast_member_id.in_(cast_member_ids), CastAgreement.withdrawn_at.is_(None)).all()
    days: dict[uuid.UUID, set[date]] = {}
    for row in rows:
        days.setdefault(row.cast_member_id, set()).update(row.days)
    return days


def check(db: Session, production_id: uuid.UUID, checks: list[AvailabilityCheck]) -> list[AvailabilityIssue]:
    wanted = {cid for c in checks for cid in c.cast_member_ids}
    actors = {a.id: a for a in db.query(CastMember).filter(CastMember.id.in_(wanted), CastMember.production_id == production_id).all()}
    if wanted - actors.keys():
        raise CastNotOnProduction("checks must name cast members of this production")
    agreed = agreed_days(db, wanted)
    issues = []
    for c in checks:
        for cid in dict.fromkeys(c.cast_member_ids):
            days = agreed.get(cid)
            if days is not None and c.shoot_date in days:
                continue
            actor = actors[cid]
            issues.append(AvailabilityIssue(
                shoot_date=c.shoot_date, cast_member_id=cid, name=actor.contact.name, character_name=actor.character_name,
                status="not_entered" if days is None else "outside", agreed_days=sorted(days or ()),
            ))
    return issues

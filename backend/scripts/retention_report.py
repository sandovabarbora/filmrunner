"""Dry-run report for the data-retention policy proposed in docs/ops/data-retention.md (FR-74).

Read-only: opens the configured database with the app's own SessionLocal and
only ever SELECTs. Never deletes anything, never needs an account beyond the
database URL the app itself already uses. Run by a human (or a future,
explicitly-approved scheduled job), never automatically.

Usage:
    cd backend && python -m scripts.retention_report
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.call_sheet import CrewCallEntry
from app.models.production import CastMember, Contact, CrewMember, Production, ProductionStatus
from app.models.push import PushSubscription
from app.models.seen import RevisionView


def main() -> None:
    db = SessionLocal()
    try:
        wrapped = db.scalars(
            select(Production).where(Production.status == ProductionStatus.WRAPPED).order_by(Production.created_at)
        ).all()

        print("== Wrapped productions (proposed 12-month policy would eventually affect these) ==")
        if not wrapped:
            print("(none)")
        else:
            now = datetime.now(timezone.utc)
            for p in wrapped:
                created = p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=timezone.utc)
                age_days = (now - created).days
                contacts = db.scalar(
                    select(func.count(func.distinct(Contact.id)))
                    .select_from(Contact)
                    .join(CrewMember, CrewMember.contact_id == Contact.id)
                    .where(CrewMember.production_id == p.id)
                )
                crew = db.scalar(select(func.count()).select_from(CrewMember).where(CrewMember.production_id == p.id))
                subs = db.scalar(
                    select(func.count())
                    .select_from(PushSubscription)
                    .join(CrewMember, CrewMember.id == PushSubscription.crew_member_id)
                    .where(CrewMember.production_id == p.id)
                )
                views = db.scalar(
                    select(func.count())
                    .select_from(RevisionView)
                    .join(CrewMember, CrewMember.id == RevisionView.crew_member_id)
                    .where(CrewMember.production_id == p.id)
                )
                print(
                    f"- {p.name!r} ({p.id}): created {age_days} days ago "
                    f"[proxy only, not time-since-wrap — see docs/ops/data-retention.md]; "
                    f"{crew} crew members, {contacts} contacts, {subs} push subscriptions, {views} read receipts"
                )

        print()
        print("== Crew members whose removal would hit the FR-79 bug today (active push subscription blocks DELETE) ==")
        blocked = db.execute(
            select(CrewMember.id, Contact.name, Production.name)
            .join(Contact, Contact.id == CrewMember.contact_id)
            .join(Production, Production.id == CrewMember.production_id)
            .join(PushSubscription, PushSubscription.crew_member_id == CrewMember.id)
            .distinct()
        ).all()
        if not blocked:
            print("(none)")
        else:
            for member_id, contact_name, production_name in blocked:
                print(f"- {contact_name!r} on {production_name!r} (crew_member {member_id})")

        print()
        print("== Orphaned contacts (no crew or cast membership on any production) ==")
        crew_contact_ids = select(CrewMember.contact_id)
        cast_contact_ids = select(CastMember.contact_id)
        orphaned = db.scalars(
            select(Contact).where(Contact.id.notin_(crew_contact_ids), Contact.id.notin_(cast_contact_ids))
        ).all()
        if not orphaned:
            print("(none)")
        else:
            for c in orphaned:
                print(f"- {c.name!r} ({c.id}), has photo: {c.photo_url is not None}")

        print()
        print("This report is read-only. Nothing above was deleted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

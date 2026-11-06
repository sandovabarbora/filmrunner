import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.sandbox_tokens import issue_token, sandbox_email
from app.models.call_sheet import CallSheet, CallSheetRevision, CastCallEntry, DistributionLog, ScheduleItem
from app.models.membership import ProductionMember, ProductionRole
from app.models.production import CastMember, Contact, CrewMember, Location, Production
from app.models.seen import RevisionView
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate
from app.schemas.sandbox import SandboxPersona, SandboxSession
from app.services.call_sheets import create_call_sheet, publish_revision

SESSION_HOURS = 24
MAX_PRODUCTIONS_PER_SESSION = 12
MAX_CONTACTS_PER_SESSION = 200


def delete_production_rows(db: Session, production_ids: list[uuid.UUID]) -> None:
    """Children before parents. Only ever called with sandbox productions; no database cascade covers this chain."""
    if not production_ids:
        return
    sheet_ids = [r[0] for r in db.query(CallSheet.id).filter(CallSheet.production_id.in_(production_ids))]
    revision_ids = [r[0] for r in db.query(CallSheetRevision.id).filter(CallSheetRevision.call_sheet_id.in_(sheet_ids))] if sheet_ids else []
    db.query(ScheduleItem).filter(ScheduleItem.location_id.in_(db.query(Location.id).filter(Location.production_id.in_(production_ids)))).update({"location_id": None}, synchronize_session=False)
    if revision_ids:
        db.query(CallSheetRevision).filter(CallSheetRevision.id.in_(revision_ids)).update({"head_of_day_crew_member_id": None}, synchronize_session=False)
        for model in (ScheduleItem, CastCallEntry, DistributionLog):
            db.query(model).filter(model.revision_id.in_(revision_ids)).delete(synchronize_session=False)
    db.query(CastMember).filter(CastMember.production_id.in_(production_ids)).delete(synchronize_session=False)
    db.query(CrewMember).filter(CrewMember.production_id.in_(production_ids)).delete(synchronize_session=False)
    if revision_ids:
        db.query(CallSheetRevision).filter(CallSheetRevision.id.in_(revision_ids)).delete(synchronize_session=False)
    if sheet_ids:
        db.query(CallSheet).filter(CallSheet.id.in_(sheet_ids)).delete(synchronize_session=False)
    db.query(Location).filter(Location.production_id.in_(production_ids)).delete(synchronize_session=False)
    db.query(ProductionMember).filter(ProductionMember.production_id.in_(production_ids)).delete(synchronize_session=False)
    db.query(Production).filter(Production.id.in_(production_ids), Production.sandbox_session.is_not(None)).delete(synchronize_session=False)


def purge_expired(db: Session) -> None:
    """A whole world goes at once, measured from its oldest film. Contacts go by their own marker, never by looking unused."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=SESSION_HOURS)
    sessions = {r[0] for r in db.query(Production.sandbox_session).filter(Production.sandbox_session.is_not(None), Production.created_at < cutoff)}
    if not sessions:
        return
    delete_production_rows(db, [r[0] for r in db.query(Production.id).filter(Production.sandbox_session.in_(sessions))])
    db.query(Contact).filter(Contact.sandbox_session.in_(sessions)).delete(synchronize_session=False)


def enforce_quota(db: Session, model: type, session: str, limit: int) -> None:
    if db.query(model).filter(model.sandbox_session == session).count() >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="This test environment is full; start over with fresh data")


def live_session_count(db: Session) -> int:
    return db.query(Production.sandbox_session).filter(Production.sandbox_session.is_not(None)).distinct().count()


def _crew(db: Session, production: Production, name: str, phone: str, department: str, position: str, head: bool = False) -> CrewMember:
    contact = Contact(name=name, phone=phone, sandbox_session=production.sandbox_session, created_by="sandbox")
    db.add(contact)
    db.flush()
    member = CrewMember(production_id=production.id, contact_id=contact.id, department=department, position=position,
                        is_head_of_department=head)
    db.add(member)
    db.flush()
    return member


def _film(db: Session, session: str, name: str, members: dict[str, ProductionRole]) -> Production:
    production = Production(name=name, sandbox_session=session)
    db.add(production)
    db.flush()
    for persona, role in members.items():
        db.add(ProductionMember(production_id=production.id, email=sandbox_email(session, persona),
                                user_id=f"sandbox-{session}-{persona}", role=role, invited_by="sandbox"))
    return production


def _scene(order: int, number: str, int_ext: str, day_night: str, description: str, location: Location, eighths: int) -> dict:
    return {"order_index": order, "scene_number": number, "int_ext": int_ext, "day_night": day_night, "set_description": description,
            "location_id": location.id, "page_count_eighths": eighths}


def _simple_film(db: Session, session: str, name: str, members: dict[str, ProductionRole], when: date, crew_call: str, people: int, *, draft: bool = False, confirmed: bool = False) -> None:
    production = _film(db, session, name, members)
    crew = [_crew(db, production, f"{first} {name.split()[0]}", f"+42060000{index:04d}", "Kamera", "Asistent") for index, first in enumerate(["Petr", "Lenka", "Ondřej", "Klára", "Filip"][:people])]
    sheet = create_call_sheet(db, production.id, CallSheetCreate(
        shoot_date=when, day_number=1, day_count=20, unit_name="Hlavní štáb", draft=draft,
        initial_revision=CallSheetRevisionCreate(general_crew_call=crew_call, schedule_items=[]),
    ), created_by="sandbox")
    if confirmed:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for member in crew:
            db.add(RevisionView(revision_id=sheet.current_revision.id, crew_member_id=member.id, first_seen_at=now, confirmed_at=now))


def create_session(db: Session, today: date) -> SandboxSession:
    """One private world per visitor: nothing here is shared with another tester or with real productions."""
    session = secrets.token_hex(8)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    owner, ad, producer = ProductionRole.OWNER, ProductionRole.EDITOR, ProductionRole.VIEWER

    water = _film(db, session, "Tichá voda", {"produkcni": owner, "ad": ad, "producent": producer})
    river = Location(production_id=water.id, name="Břeh Vltavy, Troja", address="Trojská 1, Praha 7", parking_notes="Základna na štěrkovém parkovišti u loděnice.", nearest_hospital="Nemocnice Na Bulovce, Budínova 67/2, Praha 8")
    stage = Location(production_id=water.id, name="Barrandov, hala 3", address="Kříženeckého nám. 322, Praha 5", parking_notes="Vjezd bránou B, hlásit se na vrátnici.", nearest_hospital="FN Motol, V Úvalu 84, Praha 5")
    db.add_all([river, stage])
    db.flush()
    eva = _crew(db, water, "Eva Dvořáková", "+420600000101", "Režie", "1. asistentka režie", head=True)
    gaffer = _crew(db, water, "Tomáš Novák", "+420600000102", "Světla", "Hlavní osvětlovač", head=True)
    camera = _crew(db, water, "Marek Sýkora", "+420600000103", "Kamera", "Kameraman", head=True)
    sound = _crew(db, water, "Jana Bílá", "+420600000104", "Zvuk", "Mistr zvuku", head=True)
    catering = _crew(db, water, "Lída Horká", "+420600000105", "Catering", "Catering (dodavatel)")
    _crew(db, water, "Ivo Malý", "+420600000106", "Rekvizity", "Rekvizitář")
    actress_contact = Contact(name="Anna Geislerová", phone="+420600000107", sandbox_session=session, created_by="sandbox")
    db.add(actress_contact)
    db.flush()
    actress = CastMember(production_id=water.id, contact_id=actress_contact.id, character_name="MARTA")
    db.add(actress)
    db.flush()

    def revision(call: str, scenes: list[dict], gaffer_call: str | None, pickup: str, safety: str) -> dict:
        return {
            "general_crew_call": call, "shooting_call": "08:00", "head_of_day_crew_member_id": eva.id, "safety_notes": safety, "schedule_items": scenes,
            "crew_calls": [{"crew_member_id": gaffer.id, "call_time": gaffer_call, "pickup_time": None, "note": "Pre-rig haly"}] if gaffer_call else [],
            "cast_calls": [{"cast_member_id": actress.id, "status_code": "W", "pickup_time": pickup, "call_time": "06:30", "makeup_hair_time": "06:45", "on_set_time": "08:00"}],
        }

    tomorrow = today + timedelta(days=1)
    sheet = create_call_sheet(db, water.id, CallSheetCreate(
        shoot_date=tomorrow, day_number=7, day_count=24, unit_name="Hlavní štáb",
        initial_revision=CallSheetRevisionCreate(**revision("07:00", [
            _scene(1, "42", "EXT", "DAY", "BŘEH. Marta najde loďku.", river, 14),
            _scene(2, "43", "EXT", "DAY", "BŘEH. Jonas přes řeku, dron na celek.", river, 6),
            _scene(3, "17", "INT", "DAY", "KUCHYNĚ. Snídaně, dopis.", stage, 21),
        ], None, "06:00", "Břeh: záchranné vesty do 3 m od vody.")),
    ), created_by="sandbox")
    changed, _ = publish_revision(db, sheet, CallSheetRevisionCreate(**revision("06:30", [
        _scene(1, "42", "INT", "DAY", "HALA, vodní nádrž. Marta najde loďku.", stage, 14),
        _scene(2, "17", "INT", "DAY", "KUCHYNĚ. Snídaně, dopis.", stage, 21),
    ], "05:00", "05:30", "Hala: mokrá podlaha u nádrže, kabely výš. Vesty už nejsou potřeba.")), created_by="sandbox", commit=False)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current = changed.id
    db.add_all([RevisionView(revision_id=current, crew_member_id=eva.id, first_seen_at=now, confirmed_at=now),
                RevisionView(revision_id=current, crew_member_id=camera.id, first_seen_at=now, confirmed_at=now),
                RevisionView(revision_id=current, crew_member_id=sound.id, first_seen_at=now)])
    create_call_sheet(db, water.id, CallSheetCreate(
        shoot_date=tomorrow + timedelta(days=1), day_number=8, day_count=24, unit_name="Hlavní štáb",
        initial_revision=CallSheetRevisionCreate(**revision("07:00", [_scene(1, "18", "INT", "NIGHT", "KUCHYNĚ. Tatáž sestava, noc.", stage, 9)], None, "06:00", "Beze změny.")),
    ), created_by="sandbox")

    _simple_film(db, session, "Kanál", {"produkcni": owner}, tomorrow, "07:30", 3, draft=True)
    _simple_film(db, session, "Poslední léto", {"produkcni": owner, "producent": producer}, tomorrow, "06:00", 3, confirmed=True)
    _simple_film(db, session, "Nádraží", {"produkcni": owner}, today + timedelta(days=12), "08:00", 2)
    db.commit()

    def editor(key: str) -> SandboxPersona:
        return SandboxPersona(key=key, kind="editor", token=issue_token(session, key, expires_at))

    def link(key: str, personal_token: str) -> SandboxPersona:
        return SandboxPersona(key=key, kind="link", call_sheet_id=sheet.id, personal_token=personal_token)

    return SandboxSession(expires_at=expires_at, personas=[
        editor("produkcni"), editor("ad"), editor("producent"),
        link("gaffer", gaffer.personal_token), link("herecka", actress.personal_token), link("catering", catering.personal_token),
    ])

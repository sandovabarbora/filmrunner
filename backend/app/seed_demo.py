"""Seed one realistic demo production and call sheet.

Run once against a fresh database (local, or the hosted Fly/Supabase API)
so `?sheet=<id>&api=<base>` shows something real on first open instead of
an empty lookup form. Idempotent: re-running finds the existing demo
production by name and prints its call sheet id instead of duplicating it.

    cd backend && python -m app.seed_demo

Reference: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
"""

import logging

from app.database import SessionLocal
from app.models.call_sheet import CallSheetStatus
from app.models.production import Contact, Location, Production
from app.schemas.call_sheet import CallSheetCreate, CallSheetRevisionCreate, ScheduleItemCreate
from app.services.call_sheets import create_call_sheet

logger = logging.getLogger(__name__)

DEMO_PRODUCTION_NAME = "Noční směna (demo)"


def _existing_demo_call_sheet_id(db) -> str | None:
    production = db.query(Production).filter(Production.name == DEMO_PRODUCTION_NAME).first()
    if production is None:
        return None
    call_sheet = next(
        (cs for cs in production.call_sheets if cs.status != CallSheetStatus.SUPERSEDED),
        None,
    )
    return str(call_sheet.id) if call_sheet else None


def seed() -> str:
    """Create the demo production and call sheet if they don't exist yet.

    Returns:
        The demo call sheet's id (existing or newly created), as a string.
    """
    db = SessionLocal()
    try:
        existing_id = _existing_demo_call_sheet_id(db)
        if existing_id is not None:
            logger.info("Demo call sheet already exists: %s", existing_id)
            return existing_id

        production = Production(
            name=DEMO_PRODUCTION_NAME,
            working_title="Noční směna",
            production_company="FilmRunner Demo Productions",
        )
        db.add(production)
        db.flush()

        location = Location(
            production_id=production.id,
            name="Bytový dům, Žižkov",
            address="Řípská 1, Praha 3",
            parking_notes="Ulice pouze pro rezidenty; parkujte na Olšanském náměstí, 4 min pěšky.",
            nearest_hospital="Fakultní nemocnice Královské Vinohrady, Šrobárova 50, Praha 10",
        )
        db.add(location)

        gaffer_contact = Contact(name="Tomáš Novák", phone="+420 601 234 567")
        db.add(gaffer_contact)
        db.flush()

        payload = CallSheetCreate(
            shoot_date="2026-09-22",
            day_number=4,
            day_count=18,
            unit_name="Main Unit",
            initial_revision=CallSheetRevisionCreate(
                general_crew_call="18:00",
                shooting_call="19:00",
                sunrise="06:21",
                sunset="19:47",
                weather_forecast="Jasno, 14°C, vítr 8 km/h",
                safety_notes=(
                    "Noční exteriér — reflexní vesty mimo záběr povinné. "
                    "Nejbližší nemocnice viz lokace."
                ),
                created_by="seed_demo.py",
                schedule_items=[
                    ScheduleItemCreate(
                        order_index=1,
                        scene_number="42",
                        int_ext="EXT",
                        day_night="NIGHT",
                        set_description="Ulice před bytovým domem — příjezd hlídky",
                        location_id=location.id,
                        page_count_eighths=12,
                    ),
                    ScheduleItemCreate(
                        order_index=2,
                        scene_number="43",
                        int_ext="INT",
                        day_night="NIGHT",
                        set_description="Schodiště — pronásledování",
                        location_id=location.id,
                        page_count_eighths=6,
                    ),
                ],
            ),
        )
        call_sheet = create_call_sheet(db, production.id, payload)
        logger.info(
            "Seeded demo production %s with call sheet %s", production.id, call_sheet.id
        )
        return str(call_sheet.id)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    call_sheet_id = seed()
    print(call_sheet_id)

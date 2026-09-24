"""FR-86 regression test: `backend/tests/conftest.py`'s usual `db_session`
fixture builds its schema with `Base.metadata.create_all`, which always
sends the Postgres enum labels SQLAlchemy computes from the current model
(uppercase for every `DistributionChannel` member, `PUSH` included) — so it
cannot, by construction, catch a drift between what a *migration* actually
put in the database and what the model expects. This test instead builds
its schema by running the real Alembic chain against a dedicated database,
the same path `fly.toml`'s release step and CI use, and exercises the
exact path that broke: writing and reading back a `DistributionLog` row
with `channel=DistributionChannel.PUSH`.
"""

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION_TEST_DB = "filmrunner_migration_enum_test"
ADMIN_DSN = "postgresql://filmrunner:filmrunner_dev@localhost:5432/postgres"
MIGRATED_URL = f"postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/{MIGRATION_TEST_DB}"


@pytest.fixture(scope="module")
def migrated_session_factory():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {MIGRATION_TEST_DB}")
        conn.execute(f"CREATE DATABASE {MIGRATION_TEST_DB}")

    previous_url = os.environ.get("FILMRUNNER_DATABASE_URL")
    os.environ["FILMRUNNER_DATABASE_URL"] = MIGRATED_URL
    try:
        from app.config import get_settings

        get_settings.cache_clear()
        alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.upgrade(alembic_cfg, "head")
    finally:
        if previous_url is None:
            os.environ.pop("FILMRUNNER_DATABASE_URL", None)
        else:
            os.environ["FILMRUNNER_DATABASE_URL"] = previous_url
        get_settings.cache_clear()

    engine = create_engine(MIGRATED_URL)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()

    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {MIGRATION_TEST_DB}")


def test_distribution_channel_enum_matches_the_orm_on_a_really_migrated_database(migrated_session_factory):
    """Every label the ORM can send (`DistributionChannel.PUSH` -> "PUSH"
    included) must already exist in the migrated database's enum type."""
    from app.models.call_sheet import CallSheet, CallSheetRevision, DistributionChannel, DistributionLog
    from app.models.production import Contact, Production

    session = migrated_session_factory()
    try:
        production = Production(name="Migration Check Co")
        session.add(production)
        session.flush()

        call_sheet = CallSheet(production_id=production.id, shoot_date="2026-09-24", day_number=1, day_count=10)
        session.add(call_sheet)
        session.flush()

        revision = CallSheetRevision(call_sheet_id=call_sheet.id, revision_letter="A")
        session.add(revision)
        session.flush()

        contact = Contact(name="Jana Novotná")
        session.add(contact)
        session.flush()

        log = DistributionLog(revision_id=revision.id, contact_id=contact.id, channel=DistributionChannel.PUSH)
        session.add(log)
        session.commit()

        log_id = log.id
        session.expire_all()

        reread = session.get(DistributionLog, log_id)
        assert reread is not None
        assert reread.channel == DistributionChannel.PUSH
    finally:
        session.rollback()
        session.close()

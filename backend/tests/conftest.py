"""Pytest fixtures: a real Postgres test database (not sqlite/mocks — this
skeleton exists to prove the schema and revision logic are right against
the actual target engine), wrapped in a transaction rolled back per test.

References:
    - SQLAlchemy testing patterns: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
    - FastAPI testing with dependency overrides: https://fastapi.tiangolo.com/tutorial/testing/
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# config.py defaults to production; the suite runs on the short dev token.
os.environ.setdefault("FILMRUNNER_ENVIRONMENT", "development")
os.environ.setdefault(
    "FILMRUNNER_DATABASE_URL",
    "postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner_test",
)

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402, F401, F403

TEST_DATABASE_URL = os.environ["FILMRUNNER_DATABASE_URL"]
_engine = create_engine(TEST_DATABASE_URL)
_TestingSessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Create all tables once for the test DB, drop them at the end.

    Uses Base.metadata.create_all rather than Alembic here: fast, and the
    Alembic migration itself is separately verified by actually running it
    (see README verification notes) rather than re-run per test.
    """
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db_session():
    """A session whose outer transaction is always rolled back, even though
    application code under test calls session.commit(). Uses SQLAlchemy
    2.0's own `join_transaction_mode="create_savepoint"` (the engine's
    built-in replacement for the older hand-rolled "begin_nested() plus an
    after_transaction_end listener that restarts it" recipe): the Session
    always issues its commits/rollbacks against a SAVEPOINT riding on top
    of the outer `transaction` below, re-opening one automatically on every
    transaction boundary — including the one a failed flush ends — so the
    outer transaction is never touched by application code and always gets
    rolled back here, clean, no matter what the test above did.

    The hand-rolled listener this replaced (FR-120) only restarted a
    SAVEPOINT on a *plain* commit; a flush that fails (e.g. an expected
    IntegrityError) ends more than one transaction level in one go, which
    the listener's own restart logic didn't fully account for and could
    leave the connection's nested-transaction bookkeeping one level off —
    reproduced deterministically by
    tests/test_call_sheets.py::TestRevisionSupersession::test_current_revision_uniqueness_is_enforced_by_the_database
    in isolation, not only as a cross-test ordering flake. `create_savepoint`
    mode's own restart logic is maintained by SQLAlchemy itself and handles
    this case correctly.

    Reference: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
    """
    connection = _engine.connect()
    transaction = connection.begin()
    session = _TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers():
    from app.config import get_settings

    return {"Authorization": f"Bearer {get_settings().api_bearer_token}"}


@pytest.fixture()
def background_tasks_share_db(db_session, monkeypatch):
    """FR-78: `app/services/notifications.py`'s *_in_background helpers open
    their own `app.database.SessionLocal()` — correct in production, where a
    request's own session has already committed for real by the time a
    background task runs. In a test, `db_session` never really commits (see
    its own docstring: commits just close a SAVEPOINT on a connection whose
    outer transaction is rolled back at teardown), so a background task's
    separate connection cannot see any of it and silently no-ops. Tests that
    exercise a code path ending in a background notify task need this so
    their assertions see what it wrote."""
    from app.services import notifications

    class _SharedSessionProxy:
        def close(self) -> None:
            pass  # the real session is closed by the db_session fixture itself

        def __getattr__(self, name):
            return getattr(db_session, name)

    monkeypatch.setattr(notifications, "SessionLocal", lambda: _SharedSessionProxy())


@pytest.fixture(autouse=True)
def _fresh_rate_limit_windows():
    """FR-51: every test starts with empty sliding windows, so the suite's own volume of public calls
    (all from the one TestClient "IP") never trips the per-IP limit."""
    from app.ratelimit import INSTANCES
    for m in INSTANCES:
        m.reset()
    yield

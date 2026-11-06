"""FR-223: the application engine's limits, checked on that engine rather than the test fixtures' own."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import SessionLocal, engine


def test_pool_is_bounded_below_the_session_pooler_limit():
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 5
    assert engine.pool.timeout() == 10


def test_every_transaction_has_a_statement_timeout():
    with SessionLocal() as db:
        assert db.execute(text("SHOW statement_timeout")).scalar() == "15s"
        db.commit()
        assert db.execute(text("SHOW statement_timeout")).scalar() == "15s"


def test_the_timeout_cancels_a_slow_statement():
    with engine.connect() as conn:
        conn.exec_driver_sql("SET LOCAL statement_timeout = 100")
        with pytest.raises(DBAPIError, match="statement timeout"):
            conn.exec_driver_sql("SELECT pg_sleep(2)")


def test_advisory_transaction_lock_still_works_under_the_timeout():
    with SessionLocal() as db:
        assert db.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('fr-223')::bigint)")).scalar() is True


def test_sql_errors_do_not_carry_bound_parameters():
    with engine.connect() as conn:
        with pytest.raises(DBAPIError) as caught:
            conn.execute(text("SELECT 1 / (:bound)::int - nonexistent_column"), {"bound": "crew-link-value"})
    assert "crew-link-value" not in str(caught.value)

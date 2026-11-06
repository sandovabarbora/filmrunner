"""SQLAlchemy engine/session setup.

References:
    - SQLAlchemy 2.0 ORM session basics: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# 40 people in minutes is about 5 requests each, so 1 to 3 per second of short queries; 10 connections cover that with
# the 40 worker threads queueing behind them, and stay under Supabase's session-pooler limit of 15 (Nano/Micro) with
# room left for the release command and a pg_dump. pool_timeout turns a stuck pool into an error the PWA can fall back
# from, connect_timeout does the same for a paused database. Do not run two machines without halving this.
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    hide_parameters=True,  # bound values include personal tokens and phone numbers, and SQL errors end up in logs
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
    connect_args={"connect_timeout": 5},
)


@event.listens_for(engine, "begin")
def _bound_statements(conn: Connection) -> None:
    # 15 s also bounds a publish waiting on the advisory lock, whose holder only runs short queries. SET LOCAL rather than
    # a connection option because it works under any pooler mode, and Alembic's own engine stays unlimited for migrations.
    conn.exec_driver_sql("SET LOCAL statement_timeout = 15000")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped DB session.

    Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-dependency
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""SQLAlchemy engine/session setup.

References:
    - SQLAlchemy 2.0 ORM session basics: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)
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

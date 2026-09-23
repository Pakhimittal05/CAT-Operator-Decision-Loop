"""SQLAlchemy engine and session utilities.

Creates a SQLite engine with WAL mode for concurrent read/write during demo.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings


def _set_sqlite_wal(dbapi_connection, connection_record):
    """Enable WAL journal mode for SQLite — allows concurrent readers during demo."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_engine(database_url: str | None = None):
    """Create a SQLAlchemy engine.

    Args:
        database_url: Override the configured database URL (used in tests).
    """
    url = database_url or settings.database_url
    engine = create_engine(url, connect_args={"check_same_thread": False}, echo=False)
    event.listen(engine, "connect", _set_sqlite_wal)
    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""Database engine and session management."""

import logging
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from dealcourier.db.models import Base

logger = logging.getLogger("dealcourier.db.engine")

_engine = None
_SessionLocal = None


def init_db(database_path: str) -> None:
    """Initialize the database engine and create all tables.

    Uses NullPool for SQLite — connections are created/closed on demand.
    This avoids QueuePool exhaustion when many sessions are opened
    concurrently (e.g. during batch evaluation).
    """
    global _engine, _SessionLocal

    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        poolclass=NullPool,
    )
    _SessionLocal = sessionmaker(bind=_engine)

    Base.metadata.create_all(_engine)
    _run_migrations(_engine)


def _run_migrations(engine) -> None:
    """Add any missing columns to existing tables."""
    insp = inspect(engine)

    # Map of (table_name, column_name) -> SQL to add it
    migrations = [
        ("search_items", "eval_hint", "ALTER TABLE search_items ADD COLUMN eval_hint TEXT"),
        ("search_items", "knowledge_base", "ALTER TABLE search_items ADD COLUMN knowledge_base TEXT"),
        ("listings", "auction_end_at", "ALTER TABLE listings ADD COLUMN auction_end_at DATETIME"),
    ]

    with engine.connect() as conn:
        for table, column, sql in migrations:
            if table in insp.get_table_names():
                existing = [c["name"] for c in insp.get_columns(table)]
                if column not in existing:
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"Migration: added column {table}.{column}")


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()


def get_engine():
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine

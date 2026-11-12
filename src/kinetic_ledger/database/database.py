"""
SQLAlchemy database connection management for Kinetic Ledger.

Provides:
- A configured SQLAlchemy ``Engine`` bound to PostgreSQL/pgvector.
- A scoped ``SessionLocal`` factory for request-scoped DB sessions.
- A declarative ``Base`` for all ORM models.
- A ``get_db()`` FastAPI dependency for dependency-injection.
- ``init_db()`` for creating tables and verifying connectivity.
"""

from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Docker compose uses the service name `db`; local dev can override to
# localhost by setting DATABASE_URL in the environment.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://kinetic:kinetic_password@localhost:5432/kinetic_ledger",
)

POSTGRES_POOL_SIZE: int = int(os.getenv("POSTGRES_POOL_SIZE", "5"))
POSTGRES_MAX_OVERFLOW: int = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))
POSTGRES_POOL_RECYCLE: int = int(os.getenv("POSTGRES_POOL_RECYCLE", "1800"))
POSTGRES_POOL_TIMEOUT: int = int(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
POSTGRES_ECHO: bool = os.getenv("POSTGRES_ECHO", "false").lower() in ("1", "true", "yes")

# =============================================================================
# Engine & Session Factory
# =============================================================================

def _create_engine(database_url: str = DATABASE_URL) -> Engine:
    """Create the SQLAlchemy engine with a tuned connection pool.

    Uses ``QueuePool`` so we get sane pooling defaults when running
    outside SQLite (e.g. PostgreSQL in docker compose / Cloud Run).
    """
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(
        database_url,
        echo=POSTGRES_ECHO,
        poolclass=QueuePool,
        pool_size=POSTGRES_POOL_SIZE,
        max_overflow=POSTGRES_MAX_OVERFLOW,
        pool_recycle=POSTGRES_POOL_RECYCLE,
        pool_timeout=POSTGRES_POOL_TIMEOUT,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine: Engine = _create_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base class for all Kinetic Ledger ORM models."""

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience
        cols = ", ".join(
            f"{c.name}={getattr(self, c.name)!r}"
            for c in self.__table__.columns
        )
        return f"<{self.__class__.__name__}({cols})>"


# =============================================================================
# Session Dependency
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session.

    The session is always closed, even if the route raises an exception.

    Example:
        ```python
        @app.get("/items/{item_id}")
        def read_item(item_id: int, db: Session = Depends(get_db)):
            return db.get(Item, item_id)
        ```
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# Lifecycle Helpers
# =============================================================================

def init_db() -> None:
    """Create all tables and verify the database is reachable.

    Call from FastAPI ``startup``/``lifespan`` or from CLI scripts.

    Note: As ORM models are added, import their modules here so their
    tables get registered on ``Base.metadata`` before ``create_all`` runs.
    """
    # Import the model package so all mapped tables share and register with this
    # module's Base.metadata before create_all runs.
    from .. import models  # noqa: F401

    logger.info("Creating database tables (if not already present)...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")

    # Verify connectivity / version.
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.scalar()
        logger.info("Connected to PostgreSQL: %s", version)


def check_database_connection() -> bool:
    """Return ``True`` if the database is reachable, ``False`` otherwise."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Database connectivity check failed: %s", exc)
        return False


def dispose_engine() -> None:
    """Dispose of the engine's connection pool (e.g. on shutdown)."""
    engine.dispose()
    logger.info("Database engine disposed.")

"""Async SQLAlchemy session management for the Security Monitoring System.

Provides database engine creation, session factory, and utility functions
for initializing tables and checking connectivity.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import AppConfig
from backend.db.models import Base

logger = logging.getLogger(__name__)

# Module-level references initialized by configure()
_engine = None
_session_factory = None


def configure(config: AppConfig) -> None:
    """Initialize the async engine and session factory from application config.

    Must be called once during application startup before any database access.
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        config.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the configured session factory.

    Raises RuntimeError if configure() has not been called.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database session factory not initialized. Call configure() first."
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator that yields a database session.

    Intended for use as a FastAPI dependency. The session is automatically
    closed when the request completes.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database session factory not initialized. Call configure() first."
        )

    async with _session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Create all database tables defined in the ORM models.

    Uses run_sync to execute the synchronous create_all within
    the async engine context.
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call configure() first.")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")


async def check_db_connection() -> bool:
    """Check database connectivity by executing a simple query.

    Returns:
        True if the database is reachable, False otherwise.
    """
    if _engine is None:
        return False

    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database connection check failed: %s", exc)
        return False

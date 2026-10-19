"""SQLAlchemy async engine and session factory."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


def create_engine(settings: Settings):
    """Create async engine with appropriate settings for SQLite or PostgreSQL."""
    connect_args = {}
    if "sqlite" in settings.database_url:
        connect_args["timeout"] = 10  # busy timeout in seconds

    engine = create_async_engine(
        settings.database_url,
        echo=settings.app_env.value == "development",
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    # Enable WAL mode for SQLite
    if "sqlite" in settings.database_url:

        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

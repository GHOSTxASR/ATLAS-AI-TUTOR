from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()
_engine: AsyncEngine | None = None
_session_factory = None


def _create_engine(settings) -> AsyncEngine:
    db_path = (settings.paths.sqlite_dir / "learningos.db").as_posix()
    created_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=settings.server.log_level.lower() == "debug",
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(created_engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

    return created_engine


def _configure(settings) -> None:
    global _engine, _session_factory, _settings
    _settings = settings
    _engine = _create_engine(settings)
    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


_configure(_settings)


def async_session() -> AsyncSession:
    """Return a session from the engine configured during application startup."""
    return _session_factory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for injecting SQLAlchemy sessions into FastAPI routes."""
    async with async_session() as session:
        yield session


async def init_database(settings=None) -> None:
    """Configure the database from the same settings used by migrations."""
    active_settings = settings or get_settings()
    if active_settings.paths.sqlite_dir != _settings.paths.sqlite_dir:
        await close_database()
        _configure(active_settings)
    active_settings.paths.sqlite_dir.mkdir(parents=True, exist_ok=True)


async def close_database() -> None:
    """Close the database connection pool gracefully."""
    if _engine is not None:
        await _engine.dispose()

"""
database.py
-----------
SQLAlchemy (async) engine, session factory, and startup initialisation.
Uses aiosqlite as the async driver for SQLite.
"""

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def resolve_database_url() -> str:
    """Resolves the database URL, ensuring SQLite files resolve to the populated database."""
    url = settings.database_url
    if "sqlite" in url:
        cwd = Path.cwd()
        app_dir = Path(__file__).resolve().parent
        backend_dir = app_dir.parent

        candidates = [
            backend_dir / "recoup.db",
            cwd / "recoup" / "backend" / "recoup.db",
            cwd / "backend" / "recoup.db",
            cwd / "recoup.db",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.stat().st_size > 1000:
                posix_path = candidate.resolve().as_posix()
                return f"sqlite+aiosqlite:///{posix_path}"
    return url


# ── Engine ─────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    resolve_database_url(),
    echo=settings.debug,
    connect_args={"check_same_thread": False},  # needed for SQLite
)

# ── Session factory ────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative base (shared by all ORM models) ────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    """Yields a database session; commits on success, rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Startup helper ─────────────────────────────────────────────────────────────
async def init_db() -> None:
    """Create all tables defined in db/base.py (safe to call on every startup)."""
    # Import here to ensure ORM models are registered before create_all
    from app.db import base as _  # noqa: F401
    from app.db.base import Transaction
    from sqlalchemy import func, select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed initial demo dataset if database is brand new and empty (e.g. fresh cloud container)
    try:
        async with AsyncSessionLocal() as session:
            count_res = await session.execute(select(func.count(Transaction.id)))
            count = count_res.scalar() or 0
            if count == 0:
                import sqlite3
                from generate_data import build_dataset, find_db_path, insert_records
                db_file = find_db_path()
                if db_file.exists():
                    conn = sqlite3.connect(str(db_file))
                    try:
                        records = build_dataset()
                        insert_records(conn, records)
                    finally:
                        conn.close()
    except Exception:
        # Non-fatal fallback: do not interrupt startup if auto-seeding is skipped
        pass

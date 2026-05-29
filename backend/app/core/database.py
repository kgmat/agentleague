"""Async SQLAlchemy engine, session factory, and declarative base.

Works with both SQLite (zero-config local) and Postgres (Docker). A small
``init_db`` helper creates tables on startup so the platform is usable without
running migrations, while Alembic remains available for real schema evolution.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


# ``check_same_thread`` only applies to SQLite; passed conditionally below.
_connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create all tables. Idempotent; safe to call on every startup.

    Also performs tiny additive column migrations for pre-existing databases
    (we use create_all rather than Alembic for zero-config local runs, and
    create_all does not add new columns to existing tables).
    """
    # Import models so they register on ``Base.metadata`` before create_all.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


def _add_missing_columns(sync_conn) -> None:
    """Best-effort additive migration for columns added after a DB was created.

    New columns are added WITH a default (SQLite backfills existing rows), and we
    additionally backfill any NULLs left by an earlier column-add that omitted the
    default — so non-nullable fields never serialise as None.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    # (table, column, DDL type incl. default, backfill value for stray NULLs)
    additions = [("agents", "thinking", "BOOLEAN DEFAULT 0", 0)]
    for table, column, ddl_type, backfill in additions:
        try:
            existing = {c["name"] for c in inspector.get_columns(table)}
        except Exception:
            continue  # table doesn't exist yet (fresh create handled above)
        if column not in existing:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
        else:
            sync_conn.execute(
                text(f"UPDATE {table} SET {column} = {backfill} WHERE {column} IS NULL")
            )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

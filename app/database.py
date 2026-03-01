"""
Database Connection & Session Management

This module manages the connection pool to the PostgreSQL database using SQLAlchemy
and asyncpg. It configures the engine, creates the database if it doesn't exist,
automatically migrates tables based on Models, and provides a session dependency
(`get_session`) used by API routes and Repositories for data access.
"""

import logging
from typing import AsyncGenerator

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    pool_args = {}
    if settings.app_env == "test":
        pool_args["poolclass"] = NullPool
    else:
        pool_args["pool_size"] = settings.db_pool_size
        pool_args["max_overflow"] = settings.db_max_overflow
        pool_args["pool_timeout"] = settings.db_pool_timeout

    return create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        **pool_args,
    )


async def _ensure_database_exists() -> None:
    """Create the target database if it doesn't exist (like GORM AutoMigrate)."""
    db_name = settings.db_name

    # Connect to the default 'postgres' database to check / create
    sys_conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database="postgres",
    )
    try:
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            # CREATE DATABASE cannot run inside a transaction
            await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info("Created database: %s", db_name)
        else:
            logger.debug("Database already exists: %s", db_name)
    finally:
        await sys_conn.close()


async def init_db() -> None:
    global engine, async_session_factory

    # 1. Auto-create the database if missing
    await _ensure_database_exists()

    # 2. Connect to the target database
    engine = _build_engine()
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # 3. Auto-migrate: create / update all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 4. Run one-time schema migrations (drop removed columns, fix data)
    await _run_schema_migrations()

    logger.info(
        "Database ready: %s:%s/%s (tables auto-migrated)",
        settings.db_host,
        settings.db_port,
        settings.db_name,
    )


async def _run_schema_migrations() -> None:
    """Run one-time schema migrations that create_all cannot handle (e.g. dropping columns)."""
    assert engine is not None
    async with engine.begin() as conn:
        # Migration: Remove max_points from grading_criteria (now fixed at 10 for all questions)
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'grading_criteria' AND column_name = 'max_points'"
        ))
        if result.fetchone():
            await conn.execute(text("ALTER TABLE grading_criteria DROP COLUMN max_points"))
            logger.info("Migration: dropped max_points column from grading_criteria")

        # Migration: Set all existing questions to max_points=10
        await conn.execute(text("UPDATE questions SET max_points = 10 WHERE max_points != 10"))
        logger.debug("Migration: normalised questions.max_points to 10")

        # Migration: Add Socratic follow-up columns to assessment_question_instances
        for col, col_def in [
            ("follow_up_depth", "INTEGER NOT NULL DEFAULT 0"),
            ("parent_instance_id", "UUID"),
            ("follow_up_question_text", "TEXT"),
        ]:
            chk = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'assessment_question_instances' "
                f"AND column_name = '{col}'"
            ))
            if not chk.fetchone():
                await conn.execute(text(
                    f"ALTER TABLE assessment_question_instances ADD COLUMN {col} {col_def}"
                ))
                logger.info("Migration: added %s to assessment_question_instances", col)


async def close_db() -> None:
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert async_session_factory is not None, "Database not initialised"
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def health_check() -> bool:
    """Return True if DB is reachable."""
    if engine is None:
        return False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

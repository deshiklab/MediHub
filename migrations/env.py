"""Alembic environment supporting async SQLite development and PostgreSQL."""

import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from medihub.infrastructure import models  # noqa: F401 - register ORM metadata
from medihub.infrastructure.database import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return os.environ.get("MEDIHUB_DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(_run_async_migrations())

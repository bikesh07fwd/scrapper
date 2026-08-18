"""
alembic/env.py — Alembic migration environment.

Configured for async SQLAlchemy (asyncpg driver).
The DATABASE_URL is read from application settings — never hard-coded here.

Why async? Our application uses SQLAlchemy's asyncio extension throughout.
Alembic needs to connect using the same driver, so we use
async_engine_from_config with the asyncpg URL.
"""

import asyncio
import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Make the backend package importable when alembic is run from backend/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import models so that Base.metadata is populated before autogenerate runs.
# The noqa comments suppress "imported but unused" warnings — these imports
# have a side effect (registering models with Base.metadata).
from database import Base  # noqa: E402
from models import Job, IngestionRun, AdapterHealth  # noqa: E402, F401
from config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic config object — provides access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Inject the database URL from our application settings.
# This overrides the blank sqlalchemy.url in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object that autogenerate compares against
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — generates SQL without a live database connection.
# Useful for reviewing what a migration will do before running it.
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to the database and runs migrations.
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, connect, and run migrations synchronously."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool prevents connection pooling during migrations.
        # Migrations are short-lived; a pool would waste resources.
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        # run_sync wraps the synchronous migration runner inside the async context.
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point — called by the alembic CLI
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

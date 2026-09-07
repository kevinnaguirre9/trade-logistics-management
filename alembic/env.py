"""Alembic environment: async engine, shared metadata, one schema per module."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Importing the entity packages registers every Table on the shared metadata.
import modules.customs_clearance.src.infrastructure.database.entities  # noqa: F401
import modules.shipment.src.infrastructure.database.entities  # noqa: F401
from modules.customs_clearance.src.infrastructure.database import (
    SCHEMA as CUSTOMS_SCHEMA,
)
from modules.shared.config import get_settings
from modules.shared.database import metadata
from modules.shipment.src.infrastructure.database import SCHEMA as SHIPMENT_SCHEMA

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = metadata

MANAGED_SCHEMAS = (SHIPMENT_SCHEMA, CUSTOMS_SCHEMA)


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Restrict autogenerate to the schemas owned by this service."""
    if type_ == "table":
        return obj.schema in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live connection ('offline' mode)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        version_table_schema="public",
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on a live connection, creating module schemas first."""
    for schema in MANAGED_SCHEMAS:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        version_table_schema="public",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run the migrations within it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        # "CREATE SCHEMA" above autobegins a transaction, so Alembic sees an
        # externally-managed transaction and will not commit on its own.
        await connection.commit()

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Sessions bound to one module schema.

The outbox and inbox tables are declared once, without a schema. A worker picks
the schema it operates on through ``schema_translate_map``, so the very same
mapping reads ``shipment.outbox_messages`` in one process and
``customs.outbox_messages`` in another. Tables that name their schema
explicitly, which is every aggregate table, are untouched by the translation.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from modules.shared.config import get_settings


def create_module_engine(schema: str) -> AsyncEngine:
    """Return an engine whose unqualified tables resolve to ``schema``.

    ``NullPool`` is deliberate: the CLI processes are short-lived dispatchers
    or long-lived consumers that hold a single connection, so a pool would only
    keep idle connections around.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
    ).execution_options(schema_translate_map={None: schema})


def module_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to a schema-scoped engine."""
    return async_sessionmaker(bind=engine, expire_on_commit=False)


@asynccontextmanager
async def module_engine(schema: str) -> AsyncIterator[AsyncEngine]:
    """Open a schema-scoped engine and dispose of it on the way out."""
    engine = create_module_engine(schema)
    try:
        yield engine
    finally:
        await engine.dispose()

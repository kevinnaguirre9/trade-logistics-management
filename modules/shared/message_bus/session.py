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


async def bind_module_schema(session: AsyncSession, schema: str) -> None:
    """Resolve unqualified tables to ``schema`` for this session.

    The request-scoped session of the HTTP API is built from the shared engine,
    which has no schema translation: without this, an outbox write from a use
    case would land on an unqualified ``outbox_messages`` and fail. Call it
    before the first query of the request, so the option is applied when the
    connection is acquired. Tables that name their schema explicitly, which is
    every aggregate table, are unaffected.
    """
    await session.connection(execution_options={"schema_translate_map": {None: schema}})

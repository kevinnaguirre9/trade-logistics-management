"""Persistence of outbox rows."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.message_bus.messages.destinations import (
    MessageDestinationRegistry,
    message_destinations,
)
from modules.shared.message_bus.messages.message import IntegrationMessage
from modules.shared.message_bus.outbox.outbox_message import (
    OutboxMessage,
    OutboxStatus,
)


class OutboxMessageRepository:
    """Reads and writes the outbox of one module schema.

    The session is owned by the caller: inside an HTTP request that is the
    request-scoped session, which is exactly what makes the write
    transactional with the state change that produced the message.
    """

    def __init__(
        self,
        session: AsyncSession,
        destinations: MessageDestinationRegistry | None = None,
    ) -> None:
        self._session = session
        self._destinations = destinations or message_destinations

    async def schedule(
        self,
        message: IntegrationMessage,
        headers: dict[str, Any] | None = None,
        message_id: UUID | None = None,
    ) -> OutboxMessage:
        """Store a domain message for later dispatch, without committing."""
        row = OutboxMessage.schedule(
            message=message,
            destination=self._destinations.destination_for(message.message_type),
            headers=headers,
            message_id=message_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def find_pending(self, limit: int) -> list[OutboxMessage]:
        """Return the oldest undispatched rows, locked for this dispatcher.

        ``FOR UPDATE SKIP LOCKED`` lets several dispatchers run at once: each
        one takes a disjoint batch instead of competing for the same rows.
        """
        statement = (
            select(OutboxMessage)
            .where(OutboxMessage.status == OutboxStatus.PENDING)
            .order_by(OutboxMessage.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

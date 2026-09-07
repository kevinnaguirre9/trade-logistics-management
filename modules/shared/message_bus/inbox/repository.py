"""Persistence of inbox rows."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.message_bus.inbox.inbox_message import InboxMessage


class InboxMessageRepository:
    """Reads and writes the inbox of one module schema."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def was_handled(self, message_id: UUID, handler_name: str) -> bool:
        """Return ``True`` when this handler already processed this message."""
        statement = select(InboxMessage.id).where(
            InboxMessage.message_id == message_id,
            InboxMessage.handler_name == handler_name,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def record(
        self,
        message_id: UUID,
        message_type: str,
        handler_name: str,
    ) -> InboxMessage:
        """Mark the message as handled, without committing.

        The caller commits this together with whatever the handler changed, so
        the two can never disagree.
        """
        row = InboxMessage(
            message_id=message_id,
            message_type=message_type,
            handler_name=handler_name,
        )
        self._session.add(row)
        await self._session.flush()
        return row

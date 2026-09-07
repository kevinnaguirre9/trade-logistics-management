"""The dispatcher behind the ``dispatch-messages`` command."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.message_bus.outbox.repository import OutboxMessageRepository
from modules.shared.message_bus.rabbitmq.connection import BrokerConnection

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class OutboxMessageRelay:
    """Publishes the pending rows of one module outbox, then marks them sent.

    Delivery is at-least-once by construction: if the broker accepts a message
    and the transaction that marks it sent then fails, the row stays pending
    and is published again. Consumers deduplicate through the inbox, which is
    the other half of the same guarantee.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        connection: BrokerConnection,
    ) -> None:
        self._session_factory = session_factory
        self._connection = connection

    async def dispatch(self, limit: int) -> int:
        """Publish up to ``limit`` pending messages; return how many were sent."""
        await self._connection.declare_publisher_topology()

        async with self._session_factory() as session:
            repository = OutboxMessageRepository(session)
            pending = await repository.find_pending(limit)

            if not pending:
                logger.info("No messages pending dispatch.")
                return 0

            dispatched = 0
            for row in pending:
                try:
                    await self._connection.publish(
                        exchange=row.exchange,
                        routing_key=row.routing_key,
                        body=row.body,
                        message_id=str(row.message_id),
                        message_type=row.message_type,
                        headers=row.headers,
                    )
                except Exception:
                    # Leave the row pending: the next run picks it up again.
                    logger.exception(
                        "Failed to publish message %s of type %s.",
                        row.message_id,
                        row.message_type,
                    )
                    continue

                row.mark_as_sent()
                dispatched += 1

            await session.commit()

        logger.info("Published %s message(s).", dispatched)
        return dispatched

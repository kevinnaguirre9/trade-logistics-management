"""Runs the handlers of an incoming message, once and only once each."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.message_bus.errors import MessageHandlingError
from modules.shared.message_bus.handlers.message_handler import (
    MessageHandler,
    MessageHandlerRegistry,
)
from modules.shared.message_bus.inbox.repository import InboxMessageRepository
from modules.shared.message_bus.messages.envelope import MessageEnvelope

logger = logging.getLogger(__name__)

#: Opens a fresh session, and therefore a fresh transaction, per attempt.
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class InboxMessageDispatcher:
    """Hands one delivered message to every handler subscribed to its type.

    Two guarantees live here:

    * **Idempotency.** Each handler is skipped when the inbox already holds a
      row for ``(message_id, handler_name)``, so a redelivery is a no-op.
    * **Immediate retries.** A failing handler is retried in place a few times
      before the failure is reported, which absorbs the transient errors that a
      delayed retry through the broker would only slow down.

    Every attempt runs in its own transaction, together with the inbox row that
    records it. Handlers are independent: one failing does not undo the work of
    its siblings, and only the failed ones are retried by the broker.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        handlers: MessageHandlerRegistry,
        immediate_retries: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._handlers = handlers
        self._immediate_retries = max(immediate_retries, 0)

    def subscribed_types(self) -> tuple[str, ...]:
        """Return the message types this dispatcher can handle."""
        return self._handlers.subscribed_types()

    async def dispatch(self, envelope: MessageEnvelope) -> None:
        """Run every subscribed handler, raising if any of them failed."""
        subscribers = self._handlers.handlers_for(envelope.message_type)
        if not subscribers:
            logger.info(
                "No handler subscribed to %s; message %s ignored.",
                envelope.message_type,
                envelope.message_id,
            )
            return

        failures: list[Exception] = []
        for handler in subscribers:
            try:
                await self._run(handler, envelope)
            except Exception as error:
                failures.append(error)

        if failures:
            raise MessageHandlingError(
                f"{len(failures)} handler(s) failed for message "
                f"{envelope.message_id} of type {envelope.message_type}.",
                failures=failures,
            )

    async def _run(
        self,
        handler_type: type[MessageHandler],
        envelope: MessageEnvelope,
    ) -> None:
        """Run one handler, retrying it in place before giving up."""
        last_error: Exception | None = None

        for attempt in range(1, self._immediate_retries + 2):
            try:
                handled = await self._attempt(handler_type, envelope)
            except Exception as error:
                last_error = error
                logger.warning(
                    "Handler %s failed on attempt %s for message %s: %s",
                    handler_type.handler_name,
                    attempt,
                    envelope.message_id,
                    error,
                )
                continue

            if handled:
                logger.info(
                    "Handler %s processed message %s.",
                    handler_type.handler_name,
                    envelope.message_id,
                )
            return

        raise last_error if last_error else AssertionError("unreachable")

    async def _attempt(
        self,
        handler_type: type[MessageHandler],
        envelope: MessageEnvelope,
    ) -> bool:
        """Run one attempt in its own transaction.

        Returns ``False`` when the message was already handled, so a duplicate
        is not logged as fresh work.
        """
        async with self._session_factory() as session:
            try:
                inbox = InboxMessageRepository(session)
                already_handled = await inbox.was_handled(
                    envelope.message_id, handler_type.handler_name
                )
                if already_handled:
                    logger.info(
                        "Message %s already handled by %s; skipped.",
                        envelope.message_id,
                        handler_type.handler_name,
                    )
                    return False

                await handler_type(session).handle(envelope)
                await inbox.record(
                    message_id=envelope.message_id,
                    message_type=envelope.message_type,
                    handler_name=handler_type.handler_name,
                )
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                raise

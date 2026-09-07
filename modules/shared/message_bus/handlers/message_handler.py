"""The contract a module implements to consume a message, and its registry."""

from abc import ABC, abstractmethod
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.message_bus.messages.envelope import MessageEnvelope
from modules.shared.message_bus.messages.message import IntegrationMessage


class MessageHandler(ABC):
    """Handles one message type on behalf of one module.

    A handler is built with the session that also owns the inbox row, so the
    work it does and the record that it was done commit together.

    ``handler_name`` is the deduplication key stored in the inbox: it must stay
    stable across deployments, because renaming it makes every message look
    unhandled again.
    """

    message_type: ClassVar[str]
    handler_name: ClassVar[str]

    def __init_subclass__(cls, **object_kwargs: object) -> None:
        """Default ``handler_name`` to the subclass name."""
        super().__init_subclass__(**object_kwargs)
        if not cls.__dict__.get("handler_name"):
            cls.handler_name = cls.__name__

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @abstractmethod
    async def handle(self, envelope: MessageEnvelope) -> None:
        """Process the message. Raising asks the bus to retry."""


class MessageHandlerRegistry:
    """Maps a message type to the handlers subscribed to it.

    The consumer uses it twice: to decide whether an incoming type is of any
    interest at all, and to build the handlers for the ones that are.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[type[MessageHandler]]] = {}

    def register(self, handler: type[MessageHandler]) -> None:
        """Subscribe a handler to the message type it declares."""
        subscribers = self._handlers.setdefault(handler.message_type, [])
        if handler not in subscribers:
            subscribers.append(handler)

    def register_all(self, *handlers: type[MessageHandler]) -> None:
        """Subscribe several handlers at once."""
        for handler in handlers:
            self.register(handler)

    def handlers_for(
        self, message: str | type[IntegrationMessage]
    ) -> tuple[type[MessageHandler], ...]:
        """Return the handlers subscribed to a message type."""
        message_type = message if isinstance(message, str) else message.message_type
        return tuple(self._handlers.get(message_type, ()))

    def subscribed_types(self) -> tuple[str, ...]:
        """Return every message type this worker can handle."""
        return tuple(sorted(self._handlers))

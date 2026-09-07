"""Where each message type is published: exchange plus routing key."""

from dataclasses import dataclass

from modules.shared.message_bus.errors import UnknownMessageDestinationError
from modules.shared.message_bus.messages.message import IntegrationMessage


@dataclass(frozen=True, slots=True)
class MessageDestination:
    """The broker address a message type is published to."""

    exchange: str
    routing_key: str


class MessageDestinationRegistry:
    """Maps a message type to the destination its publisher writes it to.

    Modules register their own contracts, so the shared relay can dispatch an
    outbox row without knowing which bounded context produced it.
    """

    def __init__(self) -> None:
        self._destinations: dict[str, MessageDestination] = {}

    def register(
        self,
        message: str | type[IntegrationMessage],
        destination: MessageDestination,
    ) -> None:
        """Bind a message type to its destination, replacing any previous one."""
        self._destinations[self._type_name(message)] = destination

    def destination_for(
        self, message: str | type[IntegrationMessage]
    ) -> MessageDestination:
        """Return the destination of a message type, or raise."""
        message_type = self._type_name(message)
        try:
            return self._destinations[message_type]
        except KeyError:
            raise UnknownMessageDestinationError(
                f"No destination registered for message type '{message_type}'."
            ) from None

    def registered_types(self) -> tuple[str, ...]:
        """Return every message type known to this registry."""
        return tuple(sorted(self._destinations))

    @staticmethod
    def _type_name(message: str | type[IntegrationMessage]) -> str:
        """Accept either the message class or its wire type name."""
        return message if isinstance(message, str) else message.message_type


#: Process-wide registry the modules populate at import time.
message_destinations = MessageDestinationRegistry()

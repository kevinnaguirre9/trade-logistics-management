"""Message bus shared by every module.

Delivery is at-least-once end to end:

* the **outbox** stores a message in the same transaction as the state change
  that produced it, so nothing is published for work that rolled back;
* ``dispatch-messages`` relays those rows to RabbitMQ;
* the **inbox** records ``(message_id, handler_name)`` in the same transaction
  as the handler's own writes, so a redelivery is a no-op;
* a failing handler is retried in process, then through a TTL retry queue, and
  finally parked in the error queue.

Nothing here imports a business module: modules register their message
destinations and handlers, and the worker composition root assembles them.
"""

from modules.shared.message_bus.errors import (
    MessageBusError,
    MessageHandlingError,
    MessagePublicationError,
    UnknownMessageDestinationError,
    UnknownModuleError,
)
from modules.shared.message_bus.handlers import MessageHandler, MessageHandlerRegistry
from modules.shared.message_bus.inbox import (
    InboxMessage,
    InboxMessageDispatcher,
    InboxMessageRepository,
)
from modules.shared.message_bus.messages import (
    IntegrationMessage,
    MessageDestination,
    MessageDestinationRegistry,
    MessageEnvelope,
    message_destinations,
)
from modules.shared.message_bus.outbox import (
    OutboxMessage,
    OutboxMessageRelay,
    OutboxMessageRepository,
    OutboxStatus,
)
from modules.shared.message_bus.tables import (
    inbox_messages_table,
    outbox_messages_table,
    start_message_bus_mappers,
)

__all__ = [
    "InboxMessage",
    "InboxMessageDispatcher",
    "InboxMessageRepository",
    "IntegrationMessage",
    "MessageBusError",
    "MessageDestination",
    "MessageDestinationRegistry",
    "MessageEnvelope",
    "MessageHandler",
    "MessageHandlerRegistry",
    "MessageHandlingError",
    "MessagePublicationError",
    "OutboxMessage",
    "OutboxMessageRelay",
    "OutboxMessageRepository",
    "OutboxStatus",
    "UnknownMessageDestinationError",
    "UnknownModuleError",
    "inbox_messages_table",
    "message_destinations",
    "outbox_messages_table",
    "start_message_bus_mappers",
]

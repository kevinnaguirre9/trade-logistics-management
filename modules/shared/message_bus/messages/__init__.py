"""Message contracts: the classes and envelopes that cross the broker."""

from modules.shared.message_bus.messages.destinations import (
    MessageDestination,
    MessageDestinationRegistry,
    message_destinations,
)
from modules.shared.message_bus.messages.envelope import (
    EXCEPTION_DETAILS_HEADER,
    REDELIVERY_COUNT_HEADER,
    RETRY_ENDPOINT_HEADER,
    MessageEnvelope,
)
from modules.shared.message_bus.messages.message import IntegrationMessage

__all__ = [
    "EXCEPTION_DETAILS_HEADER",
    "REDELIVERY_COUNT_HEADER",
    "RETRY_ENDPOINT_HEADER",
    "IntegrationMessage",
    "MessageDestination",
    "MessageDestinationRegistry",
    "MessageEnvelope",
    "message_destinations",
]

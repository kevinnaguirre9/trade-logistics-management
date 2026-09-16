"""The delivery envelope handed to message handlers."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

#: Header carrying how many times a message came back through the retry queue.
REDELIVERY_COUNT_HEADER = "redelivery_count"

#: Header naming the endpoint that scheduled the retry, so a fan-out message
#: rescheduled by one consumer is not reprocessed by its siblings.
RETRY_ENDPOINT_HEADER = "retry_endpoint"

#: Header carrying the failure details attached when a message is dead-lettered.
EXCEPTION_DETAILS_HEADER = "exception_details"

#: Header attached when a message is dead-lettered, describing who failed it and
#: how to put it back. Shaped as::
#:
#:     {"name": "<bounded context>",
#:      "delivery_metadata": {"message_type": "...",
#:                            "exchange": "...",
#:                            "routing_key": "..."}}
#:
#: The exchange and routing key are the retry queue's own dead-letter pair, so
#: republishing the message to them returns it to the queue that failed it -
#: which is what lets something reading the error queue replay it later.
ENDPOINT_HEADER = "endpoint"


@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    """A message as it arrives from the broker.

    Handlers receive the decoded ``body`` plus the identity they need to stay
    idempotent; everything transport-specific stays in ``headers``.
    """

    message_id: UUID
    message_type: str
    body: dict[str, Any]
    headers: dict[str, Any] = field(default_factory=dict)

    @property
    def redelivery_count(self) -> int:
        """Return how many delayed retries this message has already had."""
        try:
            return int(self.headers.get(REDELIVERY_COUNT_HEADER, 0) or 0)
        except (TypeError, ValueError):
            return 0

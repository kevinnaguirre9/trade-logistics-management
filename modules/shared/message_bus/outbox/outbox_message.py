"""The transactional outbox row."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from modules.shared.message_bus.messages.destinations import MessageDestination
from modules.shared.message_bus.messages.message import IntegrationMessage


class OutboxStatus(StrEnum):
    """Lifecycle of an outbox row."""

    PENDING = "Pending"
    SENT = "Sent"


class OutboxMessage:
    """A message stored in the same transaction as the state that caused it.

    Pure Python: the table is attached from
    :mod:`modules.shared.message_bus.outbox.tables` through imperative mapping.
    """

    def __init__(
        self,
        message_id: UUID,
        message_type: str,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
        headers: dict[str, Any] | None = None,
        properties: dict[str, Any] | None = None,
        status: OutboxStatus = OutboxStatus.PENDING,
        sent_at: datetime | None = None,
    ) -> None:
        self.message_id = message_id
        self.message_type = message_type
        self.exchange = exchange
        self.routing_key = routing_key
        self.body = body
        self.headers = headers or {}
        self.properties = properties or {}
        self.status = status
        self.sent_at = sent_at

    @classmethod
    def schedule(
        cls,
        message: IntegrationMessage,
        destination: MessageDestination,
        headers: dict[str, Any] | None = None,
        message_id: UUID | None = None,
    ) -> "OutboxMessage":
        """Turn a domain message into the row the relay will dispatch."""
        return cls(
            message_id=message_id or uuid4(),
            message_type=message.message_type,
            exchange=destination.exchange,
            routing_key=destination.routing_key,
            body=message.to_body(),
            headers=headers or {},
        )

    def mark_as_sent(self) -> None:
        """Record that the broker accepted the message."""
        self.status = OutboxStatus.SENT
        self.sent_at = datetime.now(UTC)

    @property
    def is_sent(self) -> bool:
        """Return ``True`` once the message left the outbox."""
        return self.status is OutboxStatus.SENT

    def __repr__(self) -> str:
        """Return a debugging representation of the row."""
        return (
            f"OutboxMessage(message_id={self.message_id}, "
            f"message_type={self.message_type}, status={self.status})"
        )

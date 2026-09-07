"""AMQP connection, topology declaration, publishing, retry and dead-lettering."""

import json
import logging
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractRobustConnection,
)

from modules.shared.message_bus.errors import MessagePublicationError
from modules.shared.message_bus.messages.envelope import (
    EXCEPTION_DETAILS_HEADER,
    REDELIVERY_COUNT_HEADER,
    RETRY_ENDPOINT_HEADER,
)
from modules.shared.message_bus.rabbitmq.config import BrokerTopology

logger = logging.getLogger(__name__)

EXCHANGE_TYPES = {
    "direct": aio_pika.ExchangeType.DIRECT,
    "topic": aio_pika.ExchangeType.TOPIC,
    "fanout": aio_pika.ExchangeType.FANOUT,
    "headers": aio_pika.ExchangeType.HEADERS,
}


class BrokerConnection:
    """One robust connection and channel, plus the topology it needs.

    ``connect_robust`` reconnects on its own, so there is no bespoke reconnect
    loop here: a dropped connection is re-established and the consumer resumes.
    """

    def __init__(self, topology: BrokerTopology) -> None:
        self._topology = topology
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchanges: dict[str, AbstractExchange] = {}

    @property
    def topology(self) -> BrokerTopology:
        """Return the topology this connection was built for."""
        return self._topology

    @property
    def channel(self) -> AbstractChannel:
        """Return the open channel, or fail loudly."""
        if self._channel is None:
            raise MessagePublicationError("The broker channel is not open.")
        return self._channel

    async def __aenter__(self) -> Self:
        """Open the connection and channel."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the connection."""
        await self.close()

    async def connect(self) -> None:
        """Open a robust connection and a channel."""
        self._connection = await aio_pika.connect_robust(
            self._topology.url,
            heartbeat=self._topology.heartbeat,
        )
        self._channel = await self._connection.channel()
        logger.info("Connected to RabbitMQ as '%s'.", self._topology.app_name)

    async def close(self) -> None:
        """Close the channel and the connection."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
        self._exchanges.clear()

    async def declare_exchange(self, name: str, exchange_type: str) -> AbstractExchange:
        """Declare a durable exchange once per connection."""
        if name not in self._exchanges:
            self._exchanges[name] = await self.channel.declare_exchange(
                name,
                EXCHANGE_TYPES.get(exchange_type, aio_pika.ExchangeType.TOPIC),
                durable=True,
            )
        return self._exchanges[name]

    async def declare_publisher_topology(self) -> None:
        """Declare what a dispatcher needs: the primary exchange."""
        await self.declare_exchange(
            self._topology.primary_exchange,
            self._topology.primary_exchange_type,
        )

    async def declare_consumer_topology(self) -> AbstractQueue:
        """Declare the primary, retry and error topology, and return the queue.

        The retry queue holds nothing permanently: messages sit there for
        ``retry_message_ttl_ms`` and are then dead-lettered *back* to the
        primary exchange, which is what turns a TTL into a delayed retry.
        """
        topology = self._topology

        primary_exchange = await self.declare_exchange(
            topology.primary_exchange, topology.primary_exchange_type
        )
        retry_exchange = await self.declare_exchange(
            topology.retry_exchange, topology.retry_exchange_type
        )
        error_exchange = await self.declare_exchange(
            topology.error_exchange, topology.error_exchange_type
        )

        primary_queue = await self.channel.declare_queue(
            topology.primary_queue, durable=True
        )
        await primary_queue.bind(primary_exchange, topology.primary_binding_key)

        retry_queue = await self.channel.declare_queue(
            topology.retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": topology.retry_message_ttl_ms,
                "x-dead-letter-exchange": topology.primary_exchange,
                # Messages sitting here carry the *retry* routing key, so the
                # trip back needs the primary binding key explicitly: without
                # it they would return with a key nothing binds to and be
                # dropped. A consumer ignores retries scheduled by another
                # endpoint, so this cannot cross-feed a sibling module.
                "x-dead-letter-routing-key": topology.primary_binding_key,
            },
        )
        await retry_queue.bind(retry_exchange, topology.retry_binding_key)

        error_queue = await self.channel.declare_queue(
            topology.error_queue, durable=True
        )
        await error_queue.bind(error_exchange, topology.error_routing_key)

        await self.channel.set_qos(prefetch_count=topology.prefetch)
        return primary_queue

    async def publish(
        self,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
        message_id: str,
        message_type: str,
        headers: dict[str, Any] | None = None,
        expiration_seconds: float | None = None,
    ) -> None:
        """Publish a persistent message, failing if the broker refuses it."""
        target = self._exchanges.get(exchange)
        if target is None:
            target = await self.declare_exchange(exchange, "topic")

        message = aio_pika.Message(
            body=json.dumps(body).encode(),
            content_type="application/json",
            message_id=message_id,
            type=message_type,
            headers=headers or {},
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            expiration=expiration_seconds,
        )
        await target.publish(message, routing_key=routing_key)

    async def schedule_retry(
        self,
        message: aio_pika.abc.AbstractIncomingMessage,
        error: Exception,
    ) -> None:
        """Send the message to the retry queue, one redelivery further along."""
        topology = self._topology
        headers = dict(message.headers or {})
        redelivery_count = _redelivery_count(headers) + 1
        headers[REDELIVERY_COUNT_HEADER] = redelivery_count
        headers[RETRY_ENDPOINT_HEADER] = topology.app_name

        logger.warning(
            "Rescheduling message %s after %.1fs (delayed retry %s of %s): %s",
            message.message_id,
            topology.retry_delay_seconds,
            redelivery_count,
            topology.delayed_retries,
            error,
        )

        retry_exchange = await self.declare_exchange(
            topology.retry_exchange, topology.retry_exchange_type
        )
        await retry_exchange.publish(
            aio_pika.Message(
                body=message.body,
                content_type=message.content_type,
                message_id=message.message_id,
                type=message.type,
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=topology.retry_binding_key,
        )

    async def dead_letter(
        self,
        message: aio_pika.abc.AbstractIncomingMessage,
        error: Exception,
    ) -> None:
        """Move the message to the error queue with the failure attached."""
        topology = self._topology
        headers = dict(message.headers or {})
        headers[EXCEPTION_DETAILS_HEADER] = _exception_details(error, topology.app_name)

        logger.error(
            "Dead-lettering message %s after %s delayed retries: %s",
            message.message_id,
            topology.delayed_retries,
            error,
        )

        error_exchange = await self.declare_exchange(
            topology.error_exchange, topology.error_exchange_type
        )
        await error_exchange.publish(
            aio_pika.Message(
                body=message.body,
                content_type=message.content_type,
                message_id=message.message_id,
                type=message.type,
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=topology.error_routing_key,
        )


def _redelivery_count(headers: dict[str, Any]) -> int:
    """Read the redelivery counter, tolerating a missing or odd header."""
    try:
        return int(headers.get(REDELIVERY_COUNT_HEADER, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _exception_details(error: Exception, app_name: str) -> list[dict[str, Any]]:
    """Describe the failure, flattening an aggregate of handler errors."""
    causes = getattr(error, "failures", None) or [error]
    return [
        {
            "exception_type": type(cause).__name__,
            "message": str(cause),
            "endpoint": app_name,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        for cause in causes
    ]

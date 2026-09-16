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
    ENDPOINT_HEADER,
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
        ``retry_message_ttl_ms`` and are then dead-lettered back to the primary
        queue, which is what turns a TTL into a delayed retry.

        They come back through a direct exchange under a key naming the queue
        they failed on, and the primary queue carries a second binding for that
        key. Returning them to the primary *topic* exchange instead would hand
        the retry to every queue bound to that pattern, so a sibling module
        would be woken by work it never attempted.
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
        # Usually the retry exchange itself, in which case this is a cache hit
        # and the type argument is ignored.
        retry_return_exchange = await self.declare_exchange(
            topology.resolved_primary_retry_binding_exchange,
            topology.retry_exchange_type,
        )
        await self.declare_exchange(
            topology.resolved_retry_dead_letter_exchange,
            topology.retry_exchange_type,
        )

        primary_queue = await self.channel.declare_queue(
            topology.primary_queue, durable=True
        )
        await primary_queue.bind(primary_exchange, topology.primary_binding_key)
        # Second binding: the way back in for this queue's own expired retries.
        await primary_queue.bind(
            retry_return_exchange,
            topology.resolved_primary_retry_binding_key,
        )

        retry_queue = await self.channel.declare_queue(
            topology.retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": topology.retry_message_ttl_ms,
                # Messages sitting here carry the retry queue's own routing
                # key, so the trip back needs its key stated explicitly:
                # without it they would return under a key nothing binds to and
                # be dropped.
                "x-dead-letter-exchange": (
                    topology.resolved_retry_dead_letter_exchange
                ),
                "x-dead-letter-routing-key": (
                    topology.resolved_retry_dead_letter_routing_key
                ),
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
        """Move the message to the error queue with the failure attached.

        Two headers go with it: what went wrong, and enough about where it was
        going to put it back. The message keeps its own body, id and type, so a
        replay is a republish rather than a reconstruction.
        """
        topology = self._topology
        headers = dict(message.headers or {})
        headers[EXCEPTION_DETAILS_HEADER] = _exception_details(error)
        headers[ENDPOINT_HEADER] = _endpoint_descriptor(topology, message.type)

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


def _exception_details(error: Exception) -> list[dict[str, Any]]:
    """Describe the failure, flattening an aggregate of handler errors.

    Only what went wrong. Who it went wrong for is in the ``endpoint`` header,
    which names it once for the whole message rather than once per failure.
    """
    causes = getattr(error, "failures", None) or [error]
    return [
        {
            "exception_type": type(cause).__name__,
            "message": str(cause),
            "failed_at": datetime.now(UTC).isoformat(),
        }
        for cause in causes
    ]


def _endpoint_descriptor(
    topology: BrokerTopology,
    message_type: str | None,
) -> dict[str, Any]:
    """Describe who failed the message and how to deliver it again.

    The name is the app name, the same value the retry path already records in
    its ``retry_endpoint`` header, so one message never names its endpoint two
    different ways.

    The exchange and routing key are deliberately the retry queue's own
    dead-letter pair rather than the exchange the message first arrived on.
    That pair is the way *into this consumer's queue*: a replay service reading
    the error queue can republish to it and the message lands back where it
    failed, not fanned out to every subscriber of the original topic.
    """
    return {
        "name": topology.app_name,
        "delivery_metadata": {
            "message_type": message_type or "",
            "exchange": topology.resolved_retry_dead_letter_exchange,
            "routing_key": topology.resolved_retry_dead_letter_routing_key,
        },
    }

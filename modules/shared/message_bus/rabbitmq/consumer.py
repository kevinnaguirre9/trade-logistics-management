"""The consumer behind the ``handle-messages`` command."""

import json
import logging
from typing import Any
from uuid import UUID

from aio_pika.abc import AbstractIncomingMessage

from modules.shared.message_bus.inbox.dispatcher import InboxMessageDispatcher
from modules.shared.message_bus.messages.envelope import (
    REDELIVERY_COUNT_HEADER,
    RETRY_ENDPOINT_HEADER,
    MessageEnvelope,
)
from modules.shared.message_bus.rabbitmq.connection import BrokerConnection

logger = logging.getLogger(__name__)


class MessageConsumer:
    """Consumes the primary queue and applies the recoverability policy.

    A delivery is acknowledged in every case; what differs is where the message
    goes next:

    * handled, or already handled, or of no interest -> nothing, just the ack;
    * failed with delayed retries left -> republished to the retry queue, which
      returns it to the primary queue once its TTL expires;
    * failed with none left -> republished to the error queue.

    Acknowledging a failed delivery is deliberate: the message has already been
    copied somewhere durable, so leaving it unacked would only duplicate it.
    """

    def __init__(
        self,
        connection: BrokerConnection,
        dispatcher: InboxMessageDispatcher,
    ) -> None:
        self._connection = connection
        self._dispatcher = dispatcher

    async def consume(self) -> None:
        """Declare the topology and consume until cancelled."""
        queue = await self._connection.declare_consumer_topology()
        topology = self._connection.topology

        logger.info(
            "Waiting for messages on '%s' as '%s'. Subscribed types: [%s].",
            topology.primary_queue,
            topology.app_name,
            ", ".join(self._dispatcher.subscribed_types()) or "none",
        )

        async with queue.iterator() as deliveries:
            async for message in deliveries:
                await self.handle_delivery(message)

    async def handle_delivery(self, message: AbstractIncomingMessage) -> None:
        """Apply the policy to a single delivery."""
        headers = dict(message.headers or {})

        if not self._should_process(message, headers):
            await message.ack()
            return

        envelope = MessageEnvelope(
            message_id=UUID(str(message.message_id)),
            message_type=str(message.type),
            body=_decode(message.body),
            headers=headers,
        )

        logger.info(
            "Received %s (message %s, delayed retry %s).",
            envelope.message_type,
            envelope.message_id,
            envelope.redelivery_count,
        )

        try:
            await self._dispatcher.dispatch(envelope)
        except Exception as error:
            await self._recover(message, envelope, error)
        finally:
            await message.ack()

    def _should_process(
        self,
        message: AbstractIncomingMessage,
        headers: dict[str, Any],
    ) -> bool:
        """Decide whether this delivery is ours to handle."""
        topology = self._connection.topology

        if not message.message_id:
            logger.info("Ignored: the message carries no message_id.")
            return False

        if not message.type:
            logger.info("Ignored: message %s carries no type.", message.message_id)
            return False

        if message.type not in self._dispatcher.subscribed_types():
            logger.info(
                "Ignored: no handler subscribed to %s.",
                message.type,
            )
            return False

        redelivery_count = _redelivery_count(headers)
        retry_endpoint = headers.get(RETRY_ENDPOINT_HEADER)
        if redelivery_count > 0 and retry_endpoint != topology.app_name:
            # A retry belongs to the endpoint that scheduled it. Routing alone
            # now keeps it here - it comes back on a direct binding this queue
            # owns - so this is the second line of defence, for a deployment
            # that points two workers at one return key.
            logger.info(
                "Ignored: retry of message %s belongs to '%s'.",
                message.message_id,
                retry_endpoint,
            )
            return False

        return True

    async def _recover(
        self,
        message: AbstractIncomingMessage,
        envelope: MessageEnvelope,
        error: Exception,
    ) -> None:
        """Send a failed message to the retry queue, or to the error queue."""
        topology = self._connection.topology

        if envelope.redelivery_count >= topology.delayed_retries:
            await self._connection.dead_letter(message, error)
        else:
            await self._connection.schedule_retry(message, error)


def _decode(body: bytes) -> dict[str, Any]:
    """Decode a JSON body, tolerating an empty or malformed payload."""
    try:
        decoded = json.loads(body or b"{}")
    except (TypeError, ValueError):
        logger.warning("Could not decode the message body as JSON.")
        return {}
    return decoded if isinstance(decoded, dict) else {"value": decoded}


def _redelivery_count(headers: dict[str, Any]) -> int:
    """Read the redelivery counter, tolerating a missing or odd header."""
    try:
        return int(headers.get(REDELIVERY_COUNT_HEADER, 0) or 0)
    except (TypeError, ValueError):
        return 0

"""Broker topology, resolved from settings and overridable per invocation.

Every field can be set on the command line, which is what makes one worker
image able to serve any queue: the CLI passes the exchange, queue, binding
keys, retry policy and error queue it wants, and anything left out falls back
to the environment.
"""

from dataclasses import dataclass, replace
from typing import Self

from modules.shared.config import get_settings


@dataclass(frozen=True, slots=True)
class BrokerTopology:
    """The exchanges, queues and retry policy one worker runs against."""

    url: str
    app_name: str
    heartbeat: int

    primary_exchange: str
    primary_exchange_type: str
    primary_queue: str
    primary_binding_key: str

    retry_exchange: str
    retry_exchange_type: str
    retry_queue: str
    retry_binding_key: str
    retry_message_ttl_ms: int

    error_exchange: str
    error_exchange_type: str
    error_queue: str
    error_routing_key: str

    immediate_retries: int
    delayed_retries: int
    prefetch: int

    @classmethod
    def from_settings(cls) -> Self:
        """Build the default topology from the process environment."""
        settings = get_settings()
        return cls(
            url=settings.rabbitmq_url,
            app_name=settings.rabbitmq_app_name,
            heartbeat=settings.rabbitmq_heartbeat,
            primary_exchange=settings.rabbitmq_primary_exchange,
            primary_exchange_type=settings.rabbitmq_primary_exchange_type,
            primary_queue=settings.rabbitmq_primary_queue,
            primary_binding_key=settings.rabbitmq_primary_binding_key,
            retry_exchange=settings.rabbitmq_retry_exchange,
            retry_exchange_type=settings.rabbitmq_retry_exchange_type,
            retry_queue=settings.rabbitmq_retry_queue,
            retry_binding_key=settings.rabbitmq_retry_binding_key,
            retry_message_ttl_ms=settings.rabbitmq_retry_message_ttl_ms,
            error_exchange=settings.rabbitmq_error_exchange,
            error_exchange_type=settings.rabbitmq_error_exchange_type,
            error_queue=settings.rabbitmq_error_queue,
            error_routing_key=settings.rabbitmq_error_routing_key,
            immediate_retries=settings.rabbitmq_immediate_retries,
            delayed_retries=settings.rabbitmq_delayed_retries,
            prefetch=settings.rabbitmq_consume_limit,
        )

    def overridden_with(self, **overrides: object) -> Self:
        """Return a copy with the non-``None`` overrides applied.

        The CLI passes every option it accepts; the ones the operator did not
        type arrive as ``None`` and keep their environment value.
        """
        given = {key: value for key, value in overrides.items() if value is not None}
        return replace(self, **given)

    @property
    def retry_delay_seconds(self) -> float:
        """Return the retry queue TTL expressed in seconds."""
        return self.retry_message_ttl_ms / 1000

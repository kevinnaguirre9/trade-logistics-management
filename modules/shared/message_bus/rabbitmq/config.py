"""Broker topology, resolved from settings and overridable per invocation.

Every field can be set on the command line, which is what makes one worker
image able to serve any queue: the CLI passes the exchange, queue, binding
keys, retry policy and error queue it wants, and anything left out falls back
to the environment.
"""

from dataclasses import dataclass, replace
from typing import Self

from modules.shared.config import get_settings

#: Appended to the primary queue name when the return path is left unset, so a
#: worker consuming ``trade-logistics.customs`` gets its expired retries back
#: under ``trade-logistics.customs.retry`` and nobody else does.
RETRY_RETURN_SUFFIX = "retry"


@dataclass(frozen=True, slots=True)
class BrokerTopology:
    """The exchanges, queues and retry policy one worker runs against.

    The return path deserves a word. A message that fails is parked in the
    retry queue and dead-lettered out of it when its TTL expires. Sending it
    back to the *primary* exchange would hand it to every queue bound to that
    pattern, so a sibling module would receive a retry of work it never
    attempted. Instead it goes back through a direct exchange under a key that
    names the queue it failed on, and the primary queue carries a second
    binding for exactly that key.

    All four parts of that path are overridable; left unset they are derived
    from the primary queue, which is the only thing that has to be unique.
    """

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

    # Where an expired retry is dead-lettered to, and the second binding that
    # brings it back to this worker's queue and no other. Empty means "derive
    # it", which is resolved by the properties below.
    retry_dead_letter_exchange: str
    retry_dead_letter_routing_key: str
    primary_retry_binding_exchange: str
    primary_retry_binding_key: str

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
            retry_dead_letter_exchange=settings.rabbitmq_retry_dead_letter_exchange,
            retry_dead_letter_routing_key=(
                settings.rabbitmq_retry_dead_letter_routing_key
            ),
            primary_retry_binding_exchange=(
                settings.rabbitmq_primary_retry_binding_exchange
            ),
            primary_retry_binding_key=settings.rabbitmq_primary_retry_binding_key,
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

    @property
    def resolved_retry_dead_letter_exchange(self) -> str:
        """Return the exchange an expired retry is dead-lettered to."""
        return self.retry_dead_letter_exchange or self.retry_exchange

    @property
    def resolved_retry_dead_letter_routing_key(self) -> str:
        """Return the key an expired retry comes back under.

        Derived from the primary queue rather than from its binding key: the
        binding key is a pattern several queues may share, while the queue name
        is the one thing that identifies this consumer.
        """
        return (
            self.retry_dead_letter_routing_key
            or f"{self.primary_queue}.{RETRY_RETURN_SUFFIX}"
        )

    @property
    def resolved_primary_retry_binding_exchange(self) -> str:
        """Return the exchange the primary queue takes its retries back from."""
        return (
            self.primary_retry_binding_exchange
            or self.resolved_retry_dead_letter_exchange
        )

    @property
    def resolved_primary_retry_binding_key(self) -> str:
        """Return the key the primary queue takes its retries back under.

        Matching :attr:`resolved_retry_dead_letter_routing_key` by default is
        the whole point: the two halves of the return path only meet if the key
        the retry queue dead-letters under is the key the primary queue binds.
        """
        return (
            self.primary_retry_binding_key
            or self.resolved_retry_dead_letter_routing_key
        )

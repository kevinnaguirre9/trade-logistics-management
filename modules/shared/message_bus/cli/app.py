"""The ``dispatch-messages`` and ``handle-messages`` commands.

Both are built around one module registry, so the same worker image serves any
bounded context: ``--module`` picks the schema and the handlers, and the
remaining options describe the broker topology to run against. Anything left
out falls back to the environment, which is what makes a handler connection
"dynamic" — a new queue needs a new command line, not a new build.
"""

import asyncio
import logging

import typer

from modules.shared.config import get_settings
from modules.shared.message_bus.cli.registry import ModuleBinding, ModuleRegistry
from modules.shared.message_bus.config_logging import configure_logging
from modules.shared.message_bus.inbox.dispatcher import InboxMessageDispatcher
from modules.shared.message_bus.outbox.relay import OutboxMessageRelay
from modules.shared.message_bus.rabbitmq.config import BrokerTopology
from modules.shared.message_bus.rabbitmq.connection import BrokerConnection
from modules.shared.message_bus.rabbitmq.consumer import MessageConsumer
from modules.shared.message_bus.session import module_engine, module_session_factory
from modules.shared.message_bus.tables import start_message_bus_mappers

logger = logging.getLogger("message_bus.cli")


def build_cli(modules: ModuleRegistry) -> typer.Typer:
    """Return the worker CLI bound to the modules the process knows."""
    cli = typer.Typer(
        add_completion=False,
        help="Message bus workers: outbox dispatch and inbox handling.",
        no_args_is_help=True,
    )

    module_option = typer.Option(
        ...,
        "--module",
        "-m",
        help=f"Bounded context to work on. One of: {', '.join(modules.names())}.",
    )

    @cli.command("dispatch-messages")
    def dispatch_messages(
        module: str = module_option,
        limit: int = typer.Option(
            None,
            "--limit",
            "-l",
            help="Maximum number of pending messages to publish in one run.",
        ),
        primary_exchange: str = typer.Option(
            None, "--primary-queue-exchange", help="Exchange to publish to."
        ),
        primary_exchange_type: str = typer.Option(
            None,
            "--primary-queue-exchange-type",
            help="direct | topic | fanout | headers.",
        ),
        app_name: str = typer.Option(
            None, "--app-name", help="Endpoint name recorded on published messages."
        ),
    ) -> None:
        """Publish the pending rows of a module outbox, then mark them sent."""
        configure_logging()
        binding = modules.get(module)
        topology = BrokerTopology.from_settings().overridden_with(
            primary_exchange=primary_exchange,
            primary_exchange_type=primary_exchange_type,
            app_name=app_name,
        )
        effective_limit = limit or _default_dispatch_limit()

        asyncio.run(_dispatch(binding.schema, topology, effective_limit))

    @cli.command("handle-messages")
    def handle_messages(
        module: str = module_option,
        limit: int = typer.Option(
            None, "--limit", "-l", help="Prefetch count (unacknowledged messages)."
        ),
        primary_queue: str = typer.Option(
            None, "--primary-queue", help="Queue to consume."
        ),
        primary_binding_key: str = typer.Option(
            None, "--primary-queue-binding-key", help="Binding key of the queue."
        ),
        primary_exchange: str = typer.Option(
            None, "--primary-queue-exchange", help="Exchange the queue binds to."
        ),
        primary_exchange_type: str = typer.Option(
            None,
            "--primary-queue-exchange-type",
            help="direct | topic | fanout | headers.",
        ),
        retry_queue: str = typer.Option(
            None, "--retry-queue", help="Queue holding messages awaiting a retry."
        ),
        retry_binding_key: str = typer.Option(
            None, "--retry-queue-binding-key", help="Binding key of the retry queue."
        ),
        retry_exchange: str = typer.Option(
            None, "--retry-queue-exchange", help="Exchange of the retry queue."
        ),
        retry_exchange_type: str = typer.Option(
            None, "--retry-queue-exchange-type", help="Type of the retry exchange."
        ),
        retry_message_ttl_ms: int = typer.Option(
            None,
            "--retry-queue-message-ttl",
            help="How long a message waits in the retry queue, in milliseconds.",
        ),
        immediate_retries: int = typer.Option(
            None,
            "--immediate-retries-number",
            help="In-process retries before the message goes to the retry queue.",
        ),
        delayed_retries: int = typer.Option(
            None,
            "--delayed-retries-number",
            help="Trips through the retry queue before the error queue.",
        ),
        error_queue: str = typer.Option(
            None, "--error-queue", help="Queue receiving messages that keep failing."
        ),
        error_exchange: str = typer.Option(
            None, "--error-queue-exchange", help="Exchange of the error queue."
        ),
        error_exchange_type: str = typer.Option(
            None, "--error-queue-exchange-type", help="Type of the error exchange."
        ),
        error_routing_key: str = typer.Option(
            None, "--error-queue-routing-key", help="Routing key of the error queue."
        ),
        app_name: str = typer.Option(
            None, "--app-name", help="Endpoint name owning the retries it schedules."
        ),
    ) -> None:
        """Consume a queue and hand each message to the module handlers."""
        configure_logging()
        binding = modules.get(module)
        topology = BrokerTopology.from_settings().overridden_with(
            primary_queue=primary_queue,
            primary_binding_key=primary_binding_key,
            primary_exchange=primary_exchange,
            primary_exchange_type=primary_exchange_type,
            retry_queue=retry_queue,
            retry_binding_key=retry_binding_key,
            retry_exchange=retry_exchange,
            retry_exchange_type=retry_exchange_type,
            retry_message_ttl_ms=retry_message_ttl_ms,
            immediate_retries=immediate_retries,
            delayed_retries=delayed_retries,
            error_queue=error_queue,
            error_exchange=error_exchange,
            error_exchange_type=error_exchange_type,
            error_routing_key=error_routing_key,
            app_name=app_name,
            prefetch=limit,
        )

        asyncio.run(_consume(binding, topology))

    return cli


async def _dispatch(schema: str, topology: BrokerTopology, limit: int) -> None:
    """Run one dispatch pass over a module outbox."""
    start_message_bus_mappers()

    async with module_engine(schema) as engine:
        session_factory = module_session_factory(engine)
        async with BrokerConnection(topology) as connection:
            relay = OutboxMessageRelay(session_factory, connection)
            await relay.dispatch(limit)


async def _consume(binding: ModuleBinding, topology: BrokerTopology) -> None:
    """Consume until the process is interrupted."""
    start_message_bus_mappers()

    async with module_engine(binding.schema) as engine:
        session_factory = module_session_factory(engine)
        dispatcher = InboxMessageDispatcher(
            session_factory=session_factory,
            handlers=binding.handlers,
            immediate_retries=topology.immediate_retries,
        )
        async with BrokerConnection(topology) as connection:
            consumer = MessageConsumer(connection, dispatcher)
            try:
                await consumer.consume()
            except asyncio.CancelledError:
                logger.info("Consumer stopped.")


def _default_dispatch_limit() -> int:
    """Return the dispatch batch size configured in the environment."""
    return get_settings().rabbitmq_dispatch_limit

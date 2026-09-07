"""Composition root of the message bus workers.

The HTTP process has ``main.py``; the workers have this. It is the one place
allowed to know every module, which is what keeps the shared kernel free of any
import pointing at a bounded context.

    python worker.py dispatch-messages --module shipment
    python worker.py handle-messages --module customs_clearance \
        --primary-queue trade-logistics.customs
"""

from modules.shared.config import get_settings
from modules.shared.message_bus import start_message_bus_mappers
from modules.shared.message_bus.cli import ModuleBinding, ModuleRegistry, build_cli
from modules.shared.message_bus.handlers import MessageHandlerRegistry


def build_module_registry() -> ModuleRegistry:
    """Assemble the modules a worker can be pointed at.

    Handlers are registered here as slices start consuming messages; a module
    with an empty registry can still dispatch its outbox.
    """
    settings = get_settings()

    shipment_handlers = MessageHandlerRegistry()
    customs_handlers = MessageHandlerRegistry()

    return ModuleRegistry(
        ModuleBinding(
            name="shipment",
            schema=settings.shipment_schema,
            handlers=shipment_handlers,
        ),
        ModuleBinding(
            name="customs_clearance",
            schema=settings.customs_schema,
            handlers=customs_handlers,
        ),
    )


# Destinations are deliberately not registered here: the outbox resolves them
# when a use case *writes* a message (in the API process), and the relay reads
# the exchange and routing key back off the row. A module only needs to
# register here once one of its message handlers schedules a message of its own.
start_message_bus_mappers()
cli = build_cli(build_module_registry())


if __name__ == "__main__":
    cli()

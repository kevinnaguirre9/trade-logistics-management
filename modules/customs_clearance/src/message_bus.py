"""Message composition root of the Customs Clearance module.

The counterpart of :mod:`modules.customs_clearance.src.api`: every
message-driven slice registers the handlers it owns here, so the worker mounts
one registry per module instead of reaching into the slices.
"""

from modules.customs_clearance.src.features.open_clearance_case import (
    OpenClearanceCaseMessageHandler,
)
from modules.shared.message_bus import MessageHandlerRegistry


def build_message_handlers() -> MessageHandlerRegistry:
    """Return the handlers this module subscribes to the broker with."""
    registry = MessageHandlerRegistry()
    registry.register(OpenClearanceCaseMessageHandler)
    return registry

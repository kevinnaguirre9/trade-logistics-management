"""The handler contract modules implement to consume messages."""

from modules.shared.message_bus.handlers.message_handler import (
    MessageHandler,
    MessageHandlerRegistry,
)

__all__ = [
    "MessageHandler",
    "MessageHandlerRegistry",
]

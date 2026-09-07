"""Errors raised by the message bus.

They extend the shared, framework-agnostic hierarchy so an outbox write that
fails inside an HTTP request still surfaces as an RFC 9457 problem document.
"""

from modules.shared.domain.errors import ApplicationError


class MessageBusError(ApplicationError):
    """Base class for every message bus failure."""

    status_code = 500
    title = "Message Bus Error"
    error_type = "message-bus-error"


class UnknownMessageDestinationError(MessageBusError):
    """The message type has no exchange and routing key registered."""

    error_type = "unknown-message-destination"
    title = "Unknown Message Destination"


class UnknownModuleError(MessageBusError):
    """The CLI was pointed at a module the worker does not know."""

    error_type = "unknown-module"
    title = "Unknown Module"


class MessagePublicationError(MessageBusError):
    """The broker refused, or could not confirm, the publication."""

    error_type = "message-publication-failed"
    title = "Message Publication Failed"


class MessageHandlingError(MessageBusError):
    """At least one handler failed to process a delivered message."""

    error_type = "message-handling-failed"
    title = "Message Handling Failed"

    def __init__(
        self,
        detail: str,
        *,
        failures: list[Exception] | None = None,
    ) -> None:
        super().__init__(detail)
        self.failures = failures or []

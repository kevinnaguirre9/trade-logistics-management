"""The inbox row that makes message handling idempotent."""

from uuid import UUID


class InboxMessage:
    """Records that one handler has already processed one message.

    Written in the same transaction as whatever the handler changed, so a
    redelivery finds the row and skips the work instead of repeating it.
    """

    def __init__(
        self,
        message_id: UUID,
        message_type: str,
        handler_name: str,
    ) -> None:
        self.message_id = message_id
        self.message_type = message_type
        self.handler_name = handler_name

    def __repr__(self) -> str:
        """Return a debugging representation of the row."""
        return (
            f"InboxMessage(message_id={self.message_id}, "
            f"handler_name={self.handler_name})"
        )

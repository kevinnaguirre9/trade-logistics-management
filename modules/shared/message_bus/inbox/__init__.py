"""Inbox: the record that a message was handled, and by whom."""

from modules.shared.message_bus.inbox.dispatcher import InboxMessageDispatcher
from modules.shared.message_bus.inbox.inbox_message import InboxMessage
from modules.shared.message_bus.inbox.repository import InboxMessageRepository

__all__ = [
    "InboxMessage",
    "InboxMessageDispatcher",
    "InboxMessageRepository",
]

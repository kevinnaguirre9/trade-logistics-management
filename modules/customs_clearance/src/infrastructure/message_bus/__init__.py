"""Where the messages of the Customs Clearance module are published.

Routing keys are namespaced by the module that owns the message, so a consumer
can subscribe to one behaviour (``...document-verification-completed``) or to
everything the module emits (``trade-logistics.customs.#``).
"""

from modules.customs_clearance.src.domain.events import DocumentVerificationCompleted
from modules.shared.config import get_settings
from modules.shared.message_bus import MessageDestination, message_destinations

DOCUMENT_VERIFICATION_COMPLETED_ROUTING_KEY = (
    "trade-logistics.customs.document-verification-completed"
)

_registered = False


def register_customs_message_destinations() -> None:
    """Tell the outbox where each message of this module is published."""
    global _registered
    if _registered:
        return

    exchange = get_settings().rabbitmq_primary_exchange
    message_destinations.register(
        DocumentVerificationCompleted,
        MessageDestination(
            exchange=exchange,
            routing_key=DOCUMENT_VERIFICATION_COMPLETED_ROUTING_KEY,
        ),
    )

    _registered = True


__all__ = [
    "DOCUMENT_VERIFICATION_COMPLETED_ROUTING_KEY",
    "register_customs_message_destinations",
]

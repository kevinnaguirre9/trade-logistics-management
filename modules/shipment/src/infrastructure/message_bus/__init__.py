"""Where the messages of the Shipment module are published.

Routing keys are namespaced by the module that owns the message, so a consumer
can subscribe to one behaviour (``...manifest-finalized``) or to everything the
module emits (``trade-logistics.shipment.#``).
"""

from modules.shared.config import get_settings
from modules.shared.message_bus import MessageDestination, message_destinations
from modules.shipment.src.domain.events import ShipmentManifestFinalized

SHIPMENT_MANIFEST_FINALIZED_ROUTING_KEY = "trade-logistics.shipment.manifest-finalized"

_registered = False


def register_shipment_message_destinations() -> None:
    """Tell the outbox where each message of this module is published."""
    global _registered
    if _registered:
        return

    exchange = get_settings().rabbitmq_primary_exchange
    message_destinations.register(
        ShipmentManifestFinalized,
        MessageDestination(
            exchange=exchange,
            routing_key=SHIPMENT_MANIFEST_FINALIZED_ROUTING_KEY,
        ),
    )

    _registered = True


__all__ = [
    "SHIPMENT_MANIFEST_FINALIZED_ROUTING_KEY",
    "register_shipment_message_destinations",
]

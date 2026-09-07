"""Published once the cargo manifest of a shipment is final."""

from dataclasses import dataclass

from modules.shared.message_bus import IntegrationMessage


@dataclass(frozen=True, slots=True)
class ShipmentManifestFinalized(IntegrationMessage):
    """The cargo is declared and the shipment is ready for customs.

    This is both the domain event and the contract that leaves the module:
    ``IntegrationMessage`` is a plain frozen dataclass, so the domain keeps its
    framework independence and there is no second class to keep in step.

    The payload stays deliberately thin. Customs opens a case from it and asks
    for anything else it needs, rather than this module guessing what a
    consumer might want.
    """

    shipment_id: str
    waybill_number: str
    commodity_code: str

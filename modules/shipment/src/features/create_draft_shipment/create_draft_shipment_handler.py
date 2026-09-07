"""Command handler of the *create draft shipment* slice."""

from modules.shipment.src.domain.repositories import ShipmentRepository
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId
from modules.shipment.src.domain.waybill_number_generator import (
    WaybillNumberGenerator,
)
from modules.shipment.src.features.create_draft_shipment.create_draft_shipment_command import (  # noqa: E501
    CreateDraftShipmentCommand,
)


class CreateDraftShipmentHandler:
    """Opens a shipment in ``Draft`` state and stores it.

    No integration event is emitted: creating a draft is a local setup step.
    """

    def __init__(
        self,
        shipments: ShipmentRepository,
        waybill_numbers: WaybillNumberGenerator,
    ) -> None:
        self._shipments = shipments
        self._waybill_numbers = waybill_numbers

    async def handle(self, command: CreateDraftShipmentCommand) -> Shipment:
        """Create the draft shipment and return the resulting aggregate."""
        shipment = Shipment.create(
            shipment_id=ShipmentId.generate(),
            waybill_number=await self._waybill_numbers.next(),
            origin_port_code=command.origin_port_code,
            destination_port_code=command.destination_port_code,
        )

        await self._shipments.persist(shipment)
        return shipment

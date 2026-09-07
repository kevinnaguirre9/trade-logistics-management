"""Command handler of the *assign complex route* slice."""

from modules.shipment.src.domain.exceptions import ShipmentNotFoundError
from modules.shipment.src.domain.repositories import ShipmentRepository
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId, ShipmentRoute
from modules.shipment.src.features.assign_route.assign_route_command import (
    AssignRouteCommand,
)


class AssignRouteHandler:
    """Redraws the itinerary of an existing shipment.

    No integration event is emitted: the route is internal planning data.
    """

    def __init__(self, shipments: ShipmentRepository) -> None:
        self._shipments = shipments

    async def handle(self, shipment_id: str, command: AssignRouteCommand) -> Shipment:
        """Assign the new route and return the updated aggregate."""
        identity = ShipmentId(shipment_id)

        shipment = await self._shipments.find_by_id(identity)
        if shipment is None:
            raise ShipmentNotFoundError(
                f"No shipment matches the identifier '{shipment_id}'."
            )

        shipment.assign_route(
            ShipmentRoute(
                origin_port_code=command.origin_port_code,
                destination_port_code=command.destination_port_code,
                transit_legs=tuple(command.transit_legs),
            )
        )

        await self._shipments.persist(shipment)
        return shipment

"""Command handler of the *finalize cargo manifest* slice."""

from modules.shared.message_bus import OutboxMessageRepository
from modules.shipment.src.domain.exceptions import ShipmentNotFoundError
from modules.shipment.src.domain.repositories import ShipmentRepository
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import CargoManifest, ShipmentId
from modules.shipment.src.features.finalize_manifest.finalize_manifest_command import (
    FinalizeManifestCommand,
)


class FinalizeManifestHandler:
    """Declares the cargo and announces it to the rest of the system.

    The updated aggregate and the ``ShipmentManifestFinalized`` row are written
    through the same session, so the request commits them together: customs is
    never told about a manifest that was rolled back, and a manifest is never
    stored without the announcement that follows from it.
    """

    def __init__(
        self,
        shipments: ShipmentRepository,
        outbox: OutboxMessageRepository,
    ) -> None:
        self._shipments = shipments
        self._outbox = outbox

    async def handle(
        self,
        shipment_id: str,
        command: FinalizeManifestCommand,
    ) -> Shipment:
        """Finalize the manifest and queue the integration event."""
        identity = ShipmentId(shipment_id)

        shipment = await self._shipments.find_by_id(identity)
        if shipment is None:
            raise ShipmentNotFoundError(
                f"No shipment matches the identifier '{shipment_id}'."
            )

        event = shipment.finalize_manifest(
            CargoManifest(
                total_weight_kg=command.total_weight_kg,
                total_volume_cbm=command.total_volume_cbm,
                commodity_code=command.commodity_code,
            )
        )

        await self._shipments.persist(shipment)
        await self._outbox.schedule(event)

        return shipment

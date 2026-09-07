"""Test doubles shared by the Shipment feature slices.

Kept out of the individual test modules so every slice exercises the same
in-memory substitutes for the ports declared by the domain.
"""

from modules.shipment.src.domain.repositories import ShipmentRepository
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId, WaybillNumber
from modules.shipment.src.domain.waybill_number_generator import (
    WaybillNumberGenerator,
)


class InMemoryShipmentRepository(ShipmentRepository):
    """Test double keeping the aggregates in a list.

    Pass the shipments the scenario starts from; ``persist`` appends the ones
    it does not hold yet, mirroring the insert-or-update contract of the real
    repository.
    """

    def __init__(self, *shipments: Shipment) -> None:
        self.persisted: list[Shipment] = list(shipments)

    async def persist(self, shipment: Shipment) -> None:
        if shipment not in self.persisted:
            self.persisted.append(shipment)

    async def find_by_id(self, shipment_id: ShipmentId) -> Shipment | None:
        return next(
            (item for item in self.persisted if item.id == shipment_id),
            None,
        )


class StubWaybillNumberGenerator(WaybillNumberGenerator):
    """Test double handing out a predictable waybill series."""

    def __init__(self, first_serial: int = 1) -> None:
        self._next_serial = first_serial

    async def next(self) -> WaybillNumber:
        waybill_number = WaybillNumber.from_serial(self._next_serial)
        self._next_serial += 1
        return waybill_number

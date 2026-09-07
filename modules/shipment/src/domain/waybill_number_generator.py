"""Port producing unique, structured waybill numbers."""

from abc import ABC, abstractmethod

from modules.shipment.src.domain.value_objects import WaybillNumber


class WaybillNumberGenerator(ABC):
    """Hands out the next waybill number of the carrier series."""

    @abstractmethod
    async def next(self) -> WaybillNumber:
        """Return a waybill number that has never been issued before."""

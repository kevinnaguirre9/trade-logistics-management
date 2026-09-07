"""Repository interface of the Shipment aggregate."""

from abc import ABC, abstractmethod

from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId


class ShipmentRepository(ABC):
    """Persists and retrieves whole :class:`Shipment` aggregates."""

    @abstractmethod
    async def persist(self, shipment: Shipment) -> None:
        """Insert or update the whole aggregate.

        The surrounding transaction is owned by the request/message scope, so
        implementations must not commit.
        """

    @abstractmethod
    async def find_by_id(self, shipment_id: ShipmentId) -> Shipment | None:
        """Return the aggregate with the given identity, or ``None``."""

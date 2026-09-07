"""Repository interface of the ClearanceCase aggregate."""

from abc import ABC, abstractmethod

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.value_objects import CaseId


class ClearanceCaseRepository(ABC):
    """Persists and retrieves whole :class:`ClearanceCase` aggregates."""

    @abstractmethod
    async def persist(self, clearance_case: ClearanceCase) -> None:
        """Insert or update the whole aggregate.

        The surrounding transaction is owned by the request/message scope, so
        implementations must not commit.
        """

    @abstractmethod
    async def find_by_id(self, case_id: CaseId) -> ClearanceCase | None:
        """Return the aggregate with the given identity, or ``None``."""

    @abstractmethod
    async def find_by_shipment_id(self, shipment_id: str) -> ClearanceCase | None:
        """Return the case tracking a shipment, or ``None``."""

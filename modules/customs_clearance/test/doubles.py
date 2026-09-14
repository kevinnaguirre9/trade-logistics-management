"""Test doubles shared by the Customs Clearance test suite."""

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.repositories import ClearanceCaseRepository
from modules.customs_clearance.src.domain.value_objects import CaseId


class InMemoryClearanceCaseRepository(ClearanceCaseRepository):
    """Test double keeping the aggregates in a list."""

    def __init__(self, *cases: ClearanceCase) -> None:
        self.persisted: list[ClearanceCase] = list(cases)

    async def persist(self, clearance_case: ClearanceCase) -> None:
        if clearance_case not in self.persisted:
            self.persisted.append(clearance_case)

    async def find_by_id(self, case_id: CaseId) -> ClearanceCase | None:
        return next(
            (item for item in self.persisted if item.id == case_id),
            None,
        )

    async def find_by_shipment_id(self, shipment_id: str) -> ClearanceCase | None:
        return next(
            (item for item in self.persisted if item.shipment_id == shipment_id),
            None,
        )

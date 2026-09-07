"""Command handler of the *open clearance case* slice."""

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.repositories import ClearanceCaseRepository
from modules.customs_clearance.src.domain.value_objects import CaseId
from modules.customs_clearance.src.features.open_clearance_case.open_clearance_case_command import (  # noqa: E501
    OpenClearanceCaseCommand,
)


class OpenClearanceCaseHandler:
    """Opens the regulatory case that tracks a shipment through customs.

    No message is emitted: the case only starts to interest the rest of the
    system once documents are attached and a duty is assessed.
    """

    def __init__(self, clearance_cases: ClearanceCaseRepository) -> None:
        self._clearance_cases = clearance_cases

    async def handle(self, command: OpenClearanceCaseCommand) -> ClearanceCase:
        """Open the case and return the resulting aggregate."""
        clearance_case = ClearanceCase.open_for_shipment(
            case_id=CaseId.generate(),
            shipment_id=command.shipment_id,
        )

        await self._clearance_cases.persist(clearance_case)
        return clearance_case

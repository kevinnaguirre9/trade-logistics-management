"""PostgreSQL implementation of :class:`ClearanceCaseRepository`."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.repositories import ClearanceCaseRepository
from modules.customs_clearance.src.domain.value_objects import CaseId


class PostgresClearanceCaseRepository(ClearanceCaseRepository):
    """Stores whole aggregates in ``customs.clearance_cases``.

    The session (and therefore the transaction) is owned by the caller, so the
    repository only flushes: committing is the job of the message scope.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, clearance_case: ClearanceCase) -> None:
        """Insert the aggregate, or flush the changes of a tracked one."""
        self._session.add(clearance_case)
        await self._session.flush()

    async def find_by_id(self, case_id: CaseId) -> ClearanceCase | None:
        """Return the aggregate with the given identity, or ``None``."""
        statement = select(ClearanceCase).where(ClearanceCase.id == case_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_shipment_id(self, shipment_id: str) -> ClearanceCase | None:
        """Return the case tracking a shipment, or ``None``."""
        statement = select(ClearanceCase).where(
            ClearanceCase.shipment_id == shipment_id
        )
        result = await self._session.execute(statement)
        return result.scalars().first()

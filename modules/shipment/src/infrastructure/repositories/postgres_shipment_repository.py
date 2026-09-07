"""PostgreSQL implementation of :class:`ShipmentRepository`."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shipment.src.domain.repositories import ShipmentRepository
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId


class PostgresShipmentRepository(ShipmentRepository):
    """Stores whole aggregates in ``shipment.shipments``.

    The session (and therefore the transaction) is owned by the caller, so the
    repository only flushes: committing is the job of the request scope.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, shipment: Shipment) -> None:
        """Insert the aggregate, or flush the changes of a tracked one."""
        self._session.add(shipment)
        await self._session.flush()

    async def find_by_id(self, shipment_id: ShipmentId) -> Shipment | None:
        """Return the aggregate with the given identity, or ``None``."""
        statement = select(Shipment).where(Shipment.id == shipment_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

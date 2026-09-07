"""Waybill number generator backed by a PostgreSQL sequence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shipment.src.domain.value_objects import WaybillNumber
from modules.shipment.src.domain.waybill_number_generator import (
    WaybillNumberGenerator,
)
from modules.shipment.src.infrastructure.database.entities.shipment_table import (
    waybill_serial_sequence,
)


class PostgresWaybillNumberGenerator(WaybillNumberGenerator):
    """Draws the next serial from ``shipment.waybill_serial``.

    Delegating uniqueness to a sequence keeps concurrent draft creations from
    ever colliding, and the value survives a rolled back transaction being
    reused (gaps are acceptable, duplicates are not).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next(self) -> WaybillNumber:
        """Return the next waybill number of the carrier series."""
        serial = await self._session.scalar(
            select(waybill_serial_sequence.next_value())
        )
        return WaybillNumber.from_serial(int(serial))

"""Table definitions and imperative mappings of the Shipment module.

Tables are declared against the shared metadata using the module schema, and
domain objects are attached to them with
``mapper_registry.map_imperatively(...)`` inside :func:`start_mappers`.

Note on composites: a value object mapped over a column also needs that column
mapped under a *different* attribute key, hence the ``_`` prefixed shadow
properties (``_id`` backs the ``id`` composite). Those shadows are an ORM
detail; domain code only ever touches the value objects.
"""

from sqlalchemy.orm import composite

from modules.shared.database import mapper_registry
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import (
    CargoManifest,
    ShipmentId,
    ShipmentRoute,
    WaybillNumber,
)
from modules.shipment.src.infrastructure.database.entities.shipment_table import (
    shipments_table,
    tracking_status_type,
    waybill_serial_sequence,
)

__all__ = [
    "shipments_table",
    "start_mappers",
    "tracking_status_type",
    "waybill_serial_sequence",
]

_mappers_started = False


def start_mappers() -> None:
    """Attach the Shipment domain objects to their tables (idempotent).

    Called once by the application composition root at start-up.
    """
    global _mappers_started
    if _mappers_started:
        return

    columns = shipments_table.c

    mapper_registry.map_imperatively(
        Shipment,
        shipments_table,
        properties={
            "_id": columns.id,
            "id": composite(ShipmentId, columns.id),
            "_waybill_number": columns.waybill_number,
            "waybill_number": composite(WaybillNumber, columns.waybill_number),
            "_total_weight_kg": columns.total_weight_kg,
            "_total_volume_cbm": columns.total_volume_cbm,
            "_commodity_code": columns.commodity_code,
            # Factory (not the class itself) so an all-NULL manifest loads as
            # None instead of an invalid value object.
            "manifest": composite(
                CargoManifest.from_columns,
                columns.total_weight_kg,
                columns.total_volume_cbm,
                columns.commodity_code,
            ),
            "_origin_port_code": columns.origin_port_code,
            "_destination_port_code": columns.destination_port_code,
            "_transit_legs": columns.transit_legs,
            "route": composite(
                ShipmentRoute,
                columns.origin_port_code,
                columns.destination_port_code,
                columns.transit_legs,
            ),
        },
        # Auditing columns are infrastructure only: the database maintains them.
        exclude_properties=["created_at", "updated_at"],
    )

    _mappers_started = True

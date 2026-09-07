"""Immutable value objects of the Shipment module.

Mapped with SQLAlchemy composites, so each one implements
``__composite_values__`` and value-based equality.
"""

from modules.shipment.src.domain.value_objects.cargo_manifest import CargoManifest
from modules.shipment.src.domain.value_objects.shipment_id import ShipmentId
from modules.shipment.src.domain.value_objects.shipment_route import ShipmentRoute
from modules.shipment.src.domain.value_objects.waybill_number import WaybillNumber

__all__ = [
    "CargoManifest",
    "ShipmentId",
    "ShipmentRoute",
    "WaybillNumber",
]

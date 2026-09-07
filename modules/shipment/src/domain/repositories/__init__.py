"""Repository interfaces of the Shipment module.

One repository per aggregate root, exposing whole-aggregate persistence
(``persist``) and lookup (``find_by_id``) only.
"""

from modules.shipment.src.domain.repositories.shipment_repository import (
    ShipmentRepository,
)

__all__ = ["ShipmentRepository"]

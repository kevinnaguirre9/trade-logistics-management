"""Business domain events of the Shipment module."""

from modules.shipment.src.domain.events.shipment_manifest_finalized import (
    ShipmentManifestFinalized,
)

__all__ = ["ShipmentManifestFinalized"]

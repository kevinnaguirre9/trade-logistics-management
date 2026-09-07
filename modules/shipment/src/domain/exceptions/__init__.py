"""Domain exceptions of the Shipment module.

They subclass the shared, framework-agnostic hierarchy in
``modules.shared.domain.errors`` so the HTTP layer can translate them into
RFC 9457 Problem Details without extra mapping code.
"""

from modules.shipment.src.domain.exceptions.shipment_exceptions import (
    InvalidCargoManifestError,
    InvalidShipmentIdError,
    InvalidShipmentRouteError,
    InvalidWaybillNumberError,
    RouteNotModifiableError,
    ShipmentNotFoundError,
)

__all__ = [
    "InvalidCargoManifestError",
    "InvalidShipmentIdError",
    "InvalidShipmentRouteError",
    "InvalidWaybillNumberError",
    "RouteNotModifiableError",
    "ShipmentNotFoundError",
]

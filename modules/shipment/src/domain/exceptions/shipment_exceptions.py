"""Domain exceptions raised by the Shipment aggregate and its value objects.

They extend the shared, framework-agnostic hierarchy, so the HTTP layer turns
them into RFC 9457 problem documents without any per-slice mapping code.
"""

from modules.shared.domain.errors import InvariantViolationError


class InvalidShipmentIdError(InvariantViolationError):
    """The supplied shipment identifier is not a valid UUID."""

    error_type = "invalid-shipment-id"
    title = "Invalid Shipment Identifier"


class InvalidWaybillNumberError(InvariantViolationError):
    """The waybill number does not follow the carrier format."""

    error_type = "invalid-waybill-number"
    title = "Invalid Waybill Number"


class InvalidCargoManifestError(InvariantViolationError):
    """The cargo manifest violates one of its invariants."""

    error_type = "invalid-cargo-manifest"
    title = "Invalid Cargo Manifest"


class InvalidShipmentRouteError(InvariantViolationError):
    """The route violates one of its invariants."""

    error_type = "invalid-shipment-route"
    title = "Invalid Shipment Route"

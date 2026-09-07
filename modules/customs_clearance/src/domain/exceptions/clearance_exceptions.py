"""Domain exceptions raised by the ClearanceCase aggregate and its value objects.

They extend the shared, framework-agnostic hierarchy, so the HTTP layer and the
message handlers turn them into RFC 9457 problem documents without any
per-slice mapping code.
"""

from modules.shared.domain.errors import (
    EntityNotFoundError,
    InvariantViolationError,
)


class InvalidCaseIdError(InvariantViolationError):
    """The supplied clearance case identifier is not a valid UUID."""

    error_type = "invalid-case-id"
    title = "Invalid Case Identifier"


class InvalidShipmentReferenceError(InvariantViolationError):
    """The shipment this case refers to is missing or malformed."""

    error_type = "invalid-shipment-reference"
    title = "Invalid Shipment Reference"


class InvalidMoneyError(InvariantViolationError):
    """The monetary amount or its currency violates an invariant."""

    error_type = "invalid-money"
    title = "Invalid Monetary Amount"


class CurrencyMismatchError(InvariantViolationError):
    """Two monetary amounts in different currencies were combined."""

    error_type = "currency-mismatch"
    title = "Currency Mismatch"


class ClearanceCaseNotFoundError(EntityNotFoundError):
    """No clearance case matches the requested identifier."""

    error_type = "clearance-case-not-found"
    title = "Clearance Case Not Found"

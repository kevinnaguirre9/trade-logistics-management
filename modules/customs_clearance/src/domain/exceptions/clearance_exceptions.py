"""Domain exceptions raised by the ClearanceCase aggregate and its value objects.

They extend the shared, framework-agnostic hierarchy, so the HTTP layer and the
message handlers turn them into RFC 9457 problem documents without any
per-slice mapping code.
"""

from modules.shared.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateTransitionError,
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


class InvalidDocumentReferenceError(InvariantViolationError):
    """The document type or the file it points at is not usable."""

    error_type = "invalid-document-reference"
    title = "Invalid Document Reference"


class DocumentsNotAttachableError(InvalidStateTransitionError):
    """The case has been decided, so its paperwork is closed."""

    error_type = "documents-not-attachable"
    title = "Documents Not Attachable"


class DocumentAlreadyAttachedError(ConflictError):
    """That file is already registered against this case."""

    error_type = "document-already-attached"
    title = "Document Already Attached"


class DocumentNotFoundError(EntityNotFoundError):
    """No document with that identifier is filed against the case."""

    error_type = "document-not-found"
    title = "Document Not Found"


class DocumentNotVerifiableError(InvalidStateTransitionError):
    """The case has been decided, so its documents can no longer be cleared."""

    error_type = "document-not-verifiable"
    title = "Document Not Verifiable"


class DocumentAlreadyVerifiedError(ConflictError):
    """An inspector has already cleared that document."""

    error_type = "document-already-verified"
    title = "Document Already Verified"


class InvalidInspectorError(InvariantViolationError):
    """The inspector clearing the document is not identified."""

    error_type = "invalid-inspector"
    title = "Invalid Inspector"

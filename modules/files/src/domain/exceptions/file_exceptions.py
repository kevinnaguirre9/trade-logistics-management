"""Domain exceptions of the Files module."""

from modules.shared.domain.errors import (
    ApplicationError,
    ConflictError,
    EntityNotFoundError,
    InvariantViolationError,
)


class InvalidFileIdError(InvariantViolationError):
    """The file identifier is not a UUID."""

    error_type = "invalid-file-id"


class InvalidStorageLocationError(InvariantViolationError):
    """The requested path or file name cannot be stored safely."""

    error_type = "invalid-storage-location"


class InvalidFileReferenceError(InvariantViolationError):
    """A reference does not name the aggregate it belongs to."""

    error_type = "invalid-file-reference"


class InvalidStoredFileError(InvariantViolationError):
    """The file itself violates an invariant (empty, untyped, ...)."""

    error_type = "invalid-stored-file"


class InvalidUploadPayloadError(InvariantViolationError):
    """A multipart part that should carry JSON does not."""

    error_type = "invalid-upload-payload"


class UnknownStorageDiskError(InvariantViolationError):
    """The caller asked for a disk this deployment has not configured."""

    error_type = "unknown-storage-disk"


class StoredFileNotFoundError(EntityNotFoundError):
    """No file matches the identifier."""

    error_type = "stored-file-not-found"


class FileAlreadyStoredError(ConflictError):
    """Something is already stored at that location on that disk.

    Overwriting is refused rather than silent: the location is chosen by the
    caller, so a collision means two callers disagree about what lives there.
    """

    error_type = "file-already-stored"


class FileTooLargeError(ApplicationError):
    """The upload exceeds the configured maximum size."""

    status_code = 413
    title = "Payload Too Large"
    error_type = "file-too-large"


class StorageBackendUnavailableError(ApplicationError):
    """The disk is configured but its backend cannot be reached or imported.

    Raised when the optional driver for a cloud disk is missing from the image,
    or when the remote storage refuses the operation.
    """

    status_code = 503
    title = "Storage Backend Unavailable"
    error_type = "storage-backend-unavailable"

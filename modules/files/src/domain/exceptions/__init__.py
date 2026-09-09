"""Domain exceptions of the Files module.

They subclass the framework-agnostic hierarchy in
``modules.shared.domain.errors``, so the HTTP layer turns them into RFC 9457
Problem Details without any extra mapping.
"""

from modules.files.src.domain.exceptions.file_exceptions import (
    FileAlreadyStoredError,
    FileTooLargeError,
    InvalidFileIdError,
    InvalidFileReferenceError,
    InvalidStorageLocationError,
    InvalidStoredFileError,
    InvalidUploadPayloadError,
    StorageBackendUnavailableError,
    StoredFileNotFoundError,
    UnknownStorageDiskError,
)

__all__ = [
    "FileAlreadyStoredError",
    "FileTooLargeError",
    "InvalidFileIdError",
    "InvalidFileReferenceError",
    "InvalidStorageLocationError",
    "InvalidStoredFileError",
    "InvalidUploadPayloadError",
    "StorageBackendUnavailableError",
    "StoredFileNotFoundError",
    "UnknownStorageDiskError",
]

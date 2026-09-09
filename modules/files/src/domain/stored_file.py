"""StoredFile aggregate root."""

from typing import Any

from modules.files.src.domain.entities import FileReference
from modules.files.src.domain.exceptions import InvalidStoredFileError
from modules.files.src.domain.value_objects import FileId, StorageLocation

#: Fallback when the client sends no usable media type.
DEFAULT_CONTENT_TYPE = "application/octet-stream"

#: Longest accepted disk name and media type.
MAX_DISK_LENGTH = 32
MAX_CONTENT_TYPE_LENGTH = 255


class StoredFile:
    """One file held on one disk, with the aggregates it belongs to.

    Pure Python: persistence is attached from the infrastructure layer through
    imperative mapping, so this class knows nothing about SQLAlchemy - and
    nothing about the storage backend either. The bytes are written by a
    :class:`~modules.files.src.domain.services.FileStorage` port before the
    aggregate is registered, so this record always describes something that
    exists on the disk it names.
    """

    def __init__(
        self,
        file_id: FileId,
        disk: str,
        location: StorageLocation,
        size_bytes: int,
        content_type: str,
        checksum: str,
        metadata: dict[str, Any] | None = None,
        references: list[FileReference] | None = None,
    ) -> None:
        self.id = file_id
        self.disk = disk
        self.location = location
        self.size_bytes = size_bytes
        self.content_type = content_type
        self.checksum = checksum
        self.metadata = metadata if metadata is not None else {}
        self.references = references if references is not None else []

    @classmethod
    def register(
        cls,
        file_id: FileId,
        disk: str,
        location: StorageLocation,
        size_bytes: int,
        content_type: str,
        checksum: str,
        metadata: dict[str, Any] | None = None,
        references: list[FileReference] | None = None,
    ) -> "StoredFile":
        """Record a file that has just been written to a disk."""
        stored_file = cls(
            file_id=file_id,
            disk=cls._validated_disk(disk),
            location=location,
            size_bytes=cls._validated_size(size_bytes),
            content_type=cls._validated_content_type(content_type),
            checksum=cls._validated_checksum(checksum),
            metadata=cls._validated_metadata(metadata),
            references=[],
        )

        for reference in references or []:
            stored_file.relate_to(reference)

        return stored_file

    def relate_to(self, reference: FileReference) -> None:
        """Attach the file to an aggregate of another bounded context.

        Declaring the same owner twice is a no-op rather than an error: the
        second call says nothing the first did not.
        """
        if not isinstance(reference, FileReference):
            raise InvalidStoredFileError(
                "Only a file reference can be attached to a file."
            )

        if any(existing.points_at(reference) for existing in self.references):
            return

        self.references.append(reference)

    def is_referenced_by(
        self,
        context: str,
        entity_type: str,
        entity_id: str | None = None,
    ) -> bool:
        """Return ``True`` when the file is about that thing.

        Leaving ``entity_id`` out asks the broader question - is this file
        about that kind of thing at all - which is the only one that can be
        asked of a reference that carries no identifier.
        """
        return any(
            reference.context == context
            and reference.entity_type == entity_type
            and (entity_id is None or reference.entity_id == entity_id)
            for reference in self.references
        )

    @property
    def key(self) -> str:
        """Return the object key of the file on its disk."""
        return self.location.key

    @staticmethod
    def _validated_disk(value: object) -> str:
        """Return the disk name, or raise."""
        if not isinstance(value, str):
            raise InvalidStoredFileError("The disk must be a string.")

        disk = value.strip().lower()
        if not disk:
            raise InvalidStoredFileError("The disk is required.")
        if len(disk) > MAX_DISK_LENGTH:
            raise InvalidStoredFileError(
                f"The disk name is longer than {MAX_DISK_LENGTH} characters."
            )
        return disk

    @staticmethod
    def _validated_size(value: object) -> int:
        """Return the byte count, or raise.

        A zero-byte upload is refused: it is almost always a client that lost
        the body, and storing it would hide the failure behind a file uuid.
        """
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidStoredFileError("The size must be a whole number of bytes.")
        if value <= 0:
            raise InvalidStoredFileError("The file is empty.")
        return value

    @staticmethod
    def _validated_content_type(value: object) -> str:
        """Return the media type, defaulting when the client sent none."""
        if value is None:
            return DEFAULT_CONTENT_TYPE
        if not isinstance(value, str):
            raise InvalidStoredFileError("The content type must be a string.")

        content_type = value.strip() or DEFAULT_CONTENT_TYPE
        if len(content_type) > MAX_CONTENT_TYPE_LENGTH:
            raise InvalidStoredFileError(
                f"The content type is longer than {MAX_CONTENT_TYPE_LENGTH} characters."
            )
        return content_type

    @staticmethod
    def _validated_checksum(value: object) -> str:
        """Return the content digest, or raise."""
        if not isinstance(value, str) or not value.strip():
            raise InvalidStoredFileError("The checksum is required.")
        return value.strip()

    @staticmethod
    def _validated_metadata(value: object) -> dict[str, Any]:
        """Return the caller's metadata, or raise.

        The contents are the caller's business; the shape is not. It has to be
        a JSON object, because that is what the column holds.
        """
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise InvalidStoredFileError("The metadata must be a JSON object.")
        if any(not isinstance(key, str) for key in value):
            raise InvalidStoredFileError("Every metadata key must be a string.")
        return dict(value)

    def __repr__(self) -> str:
        """Return a debugging representation of the aggregate."""
        return (
            f"StoredFile(id={self.id}, disk={self.disk}, key={self.key}, "
            f"size_bytes={self.size_bytes})"
        )

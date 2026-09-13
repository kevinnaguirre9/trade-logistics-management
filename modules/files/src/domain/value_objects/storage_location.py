"""Where a file lives on a disk: the directory path plus the file name."""

from dataclasses import dataclass
from typing import ClassVar

from modules.files.src.domain.exceptions import InvalidStorageLocationError

#: Segments that would let a caller climb out of the path they were given.
TRAVERSAL_SEGMENTS = frozenset({"..", "."})


@dataclass(frozen=True, slots=True)
class StorageLocation:
    """A disk-agnostic object key, split into the parts the caller supplies.

    The same value addresses a directory on a local volume, an object in a GCS
    or S3 bucket, and a path on an SFTP server, because every backend the
    module supports keys objects with ``/``-separated text.

    This is the module's security boundary. The path and the name arrive from
    a client, so the invariants here are what keeps an upload inside the disk
    it was addressed to:

    * no ``..`` or ``.`` segment, so a caller cannot climb out of its prefix;
    * the name is a name, never a path: it carries no separator of its own;
    * no NUL byte, no Windows drive letter, no UNC prefix.

    Leading and trailing separators are normalized away rather than refused: a
    caller writing ``/invoices/`` means the same place as ``invoices``.
    """

    path: str
    name: str

    MAX_PATH_LENGTH: ClassVar[int] = 512
    MAX_NAME_LENGTH: ClassVar[int] = 255

    def __post_init__(self) -> None:
        """Normalize both halves and reject anything that escapes the disk."""
        object.__setattr__(self, "path", self._validated_path(self.path))
        object.__setattr__(self, "name", self._validated_name(self.name))

    @classmethod
    def _validated_path(cls, value: object) -> str:
        """Return the normalized directory prefix, or raise."""
        if value is None:
            return ""
        if not isinstance(value, str):
            raise InvalidStorageLocationError("The path must be a string.")

        candidate = value.strip().replace("\\", "/")
        cls._reject_dangerous_characters(candidate, "path")

        segments = [segment for segment in candidate.split("/") if segment]
        for segment in segments:
            if segment in TRAVERSAL_SEGMENTS:
                raise InvalidStorageLocationError(
                    f"The path '{value}' may not contain a '{segment}' segment."
                )

        normalized = "/".join(segments)
        if len(normalized) > cls.MAX_PATH_LENGTH:
            raise InvalidStorageLocationError(
                f"The path is longer than {cls.MAX_PATH_LENGTH} characters."
            )
        return normalized

    @classmethod
    def _validated_name(cls, value: object) -> str:
        """Return the file name, or raise."""
        if not isinstance(value, str):
            raise InvalidStorageLocationError("The file name must be a string.")

        candidate = value.strip()
        if not candidate:
            raise InvalidStorageLocationError("The file name is required.")

        cls._reject_dangerous_characters(candidate, "file name")

        if "/" in candidate or "\\" in candidate:
            raise InvalidStorageLocationError(
                f"The file name '{value}' may not contain a path separator; "
                "put the directory in 'path' instead."
            )
        if candidate in TRAVERSAL_SEGMENTS:
            raise InvalidStorageLocationError(f"'{value}' is not a usable file name.")
        if len(candidate) > cls.MAX_NAME_LENGTH:
            raise InvalidStorageLocationError(
                f"The file name is longer than {cls.MAX_NAME_LENGTH} characters."
            )
        return candidate

    @staticmethod
    def _reject_dangerous_characters(candidate: str, label: str) -> None:
        """Raise when the value carries something no backend should see."""
        if "\x00" in candidate:
            raise InvalidStorageLocationError(
                f"The {label} may not contain a NUL byte."
            )
        if candidate.startswith("~"):
            raise InvalidStorageLocationError(f"The {label} may not start with '~'.")
        if len(candidate) > 1 and candidate[1] == ":":
            raise InvalidStorageLocationError(
                f"The {label} may not be an absolute Windows path."
            )

    @property
    def key(self) -> str:
        """Return the object key, relative to the root of the disk."""
        return f"{self.path}/{self.name}" if self.path else self.name

    @property
    def extension(self) -> str:
        """Return the lower-cased extension, without the dot, or ``''``."""
        _, separator, extension = self.name.rpartition(".")
        return extension.lower() if separator else ""

    def __composite_values__(self) -> tuple[str, str]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.path, self.name)

    def __str__(self) -> str:
        """Return the object key."""
        return self.key

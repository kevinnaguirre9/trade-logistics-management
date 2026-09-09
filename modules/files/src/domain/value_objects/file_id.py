"""Strongly typed identity of a stored file."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from modules.files.src.domain.exceptions import InvalidFileIdError


@dataclass(frozen=True, slots=True)
class FileId:
    """A validated UUID identifying one stored file.

    This is the ``file_uuid`` other bounded contexts hold on to: they store the
    value and nothing else, exactly as customs stores a shipment identifier.
    """

    value: UUID

    def __post_init__(self) -> None:
        """Accept a UUID or its string form, and reject anything else."""
        if isinstance(self.value, UUID):
            return

        if isinstance(self.value, str):
            try:
                object.__setattr__(self, "value", UUID(self.value))
            except ValueError:
                raise InvalidFileIdError(
                    f"'{self.value}' is not a valid file identifier."
                ) from None
            return

        raise InvalidFileIdError("The file identifier must be a UUID.")

    @classmethod
    def generate(cls) -> "FileId":
        """Return a fresh identity."""
        return cls(value=uuid4())

    def equals(self, other: object) -> bool:
        """Return ``True`` when both identities are the same value."""
        return isinstance(other, FileId) and other.value == self.value

    def __composite_values__(self) -> tuple[UUID]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.value,)

    def __str__(self) -> str:
        """Return the canonical string form of the identifier."""
        return str(self.value)

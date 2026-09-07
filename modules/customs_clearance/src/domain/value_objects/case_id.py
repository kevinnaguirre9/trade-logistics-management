"""Strongly typed identity of a clearance case."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from modules.customs_clearance.src.domain.exceptions import InvalidCaseIdError


@dataclass(frozen=True, slots=True)
class CaseId:
    """A validated UUID identifying one clearance case."""

    value: UUID

    def __post_init__(self) -> None:
        """Accept a UUID or its string form, and reject anything else."""
        if isinstance(self.value, UUID):
            return

        if isinstance(self.value, str):
            try:
                object.__setattr__(self, "value", UUID(self.value))
            except ValueError:
                raise InvalidCaseIdError(
                    f"'{self.value}' is not a valid clearance case identifier."
                ) from None
            return

        raise InvalidCaseIdError("The clearance case identifier must be a UUID.")

    @classmethod
    def generate(cls) -> "CaseId":
        """Return a fresh identity."""
        return cls(value=uuid4())

    def equals(self, other: object) -> bool:
        """Return ``True`` when both identities are the same value."""
        return isinstance(other, CaseId) and other.value == self.value

    def __composite_values__(self) -> tuple[UUID]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.value,)

    def __str__(self) -> str:
        """Return the canonical string form of the identifier."""
        return str(self.value)

"""Strongly typed shipment identifier."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from modules.shipment.src.domain.exceptions import InvalidShipmentIdError


@dataclass(frozen=True, slots=True)
class ShipmentId:
    """UUID identity of a :class:`Shipment` aggregate."""

    value: UUID

    def __post_init__(self) -> None:
        """Validate (and coerce) the wrapped identifier."""
        raw = self.value
        if isinstance(raw, str):
            try:
                raw = UUID(raw)
            except ValueError as error:
                raise InvalidShipmentIdError(
                    f"'{self.value}' is not a valid shipment identifier."
                ) from error
            object.__setattr__(self, "value", raw)
        elif not isinstance(raw, UUID):
            raise InvalidShipmentIdError("A shipment identifier must be a UUID.")

    @classmethod
    def generate(cls) -> "ShipmentId":
        """Return a brand new random identifier."""
        return cls(uuid4())

    def equals(self, other: object) -> bool:
        """Return ``True`` when both identifiers hold the same UUID."""
        return self == other

    def __composite_values__(self) -> tuple[UUID]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.value,)

    def __str__(self) -> str:
        """Return the canonical string form of the identifier."""
        return str(self.value)

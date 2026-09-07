"""Carrier waybill number."""

import re
from dataclasses import dataclass

from modules.shipment.src.domain.exceptions import InvalidWaybillNumberError

#: Carrier prefix plus a seven digit serial, e.g. ``MUST-0000042``.
WAYBILL_NUMBER_PATTERN = re.compile(r"^MUST-[0-9]{7}$")


@dataclass(frozen=True, slots=True)
class WaybillNumber:
    """Structured tracking number printed on the transport document."""

    value: str

    def __post_init__(self) -> None:
        """Normalize the number and enforce the carrier format."""
        if not isinstance(self.value, str):
            raise InvalidWaybillNumberError("A waybill number must be a string.")

        normalized = self.value.strip().upper()
        if not WAYBILL_NUMBER_PATTERN.match(normalized):
            raise InvalidWaybillNumberError(
                f"'{self.value}' does not match the carrier waybill format "
                f"'{WAYBILL_NUMBER_PATTERN.pattern}'."
            )
        object.__setattr__(self, "value", normalized)

    @classmethod
    def from_serial(cls, serial: int) -> "WaybillNumber":
        """Build a waybill number from a numeric serial."""
        return cls(f"MUST-{serial:07d}")

    def equals(self, other: object) -> bool:
        """Return ``True`` when both waybill numbers hold the same value."""
        return self == other

    def __composite_values__(self) -> tuple[str]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.value,)

    def __str__(self) -> str:
        """Return the printable waybill number."""
        return self.value

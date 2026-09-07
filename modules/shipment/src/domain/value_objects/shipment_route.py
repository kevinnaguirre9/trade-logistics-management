"""Physical route followed by a shipment."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from modules.shipment.src.domain.exceptions import InvalidShipmentRouteError

#: UN/LOCODE: two letter country code plus a three character location code.
PORT_CODE_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")


@dataclass(frozen=True, slots=True)
class ShipmentRoute:
    """Origin, destination and the ordered transit legs in between.

    Invariant: the origin cannot be equal to the destination. Checking that the
    legs form a logical sequence belongs to the *assign route* use case.
    """

    origin_port_code: str
    destination_port_code: str
    transit_legs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize the port codes and enforce the route invariants."""
        origin = self._validated_port_code(self.origin_port_code, "origin port code")
        destination = self._validated_port_code(
            self.destination_port_code, "destination port code"
        )

        if origin == destination:
            raise InvalidShipmentRouteError(
                "The origin port cannot be the same as the destination port "
                f"('{origin}')."
            )

        legs = self.transit_legs or ()
        if isinstance(legs, str) or not isinstance(legs, Iterable):
            raise InvalidShipmentRouteError("The transit legs must be a sequence.")

        object.__setattr__(self, "origin_port_code", origin)
        object.__setattr__(self, "destination_port_code", destination)
        object.__setattr__(
            self,
            "transit_legs",
            tuple(self._validated_port_code(leg, "transit leg") for leg in legs),
        )

    @staticmethod
    def _validated_port_code(value: object, label: str) -> str:
        """Return the normalized UN/LOCODE or raise."""
        if not isinstance(value, str):
            raise InvalidShipmentRouteError(f"The {label} must be a string.")

        normalized = value.strip().upper()
        if not PORT_CODE_PATTERN.match(normalized):
            raise InvalidShipmentRouteError(
                f"'{value}' is not a valid {label}; expected a UN/LOCODE such "
                "as 'ESVLC'."
            )
        return normalized

    def __composite_values__(self) -> tuple[str, str, list[str]]:
        """Return the column values used by the SQLAlchemy composite."""
        return (
            self.origin_port_code,
            self.destination_port_code,
            list(self.transit_legs),
        )

    def __str__(self) -> str:
        """Return the route as ``ORIGIN > LEG > DESTINATION``."""
        hops: Sequence[str] = (
            self.origin_port_code,
            *self.transit_legs,
            self.destination_port_code,
        )
        return " > ".join(hops)

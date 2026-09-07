"""Declared content of the cargo."""

from dataclasses import dataclass

from modules.shipment.src.domain.exceptions import InvalidCargoManifestError

MAX_COMMODITY_CODE_LENGTH = 16


@dataclass(frozen=True, slots=True)
class CargoManifest:
    """Weight, volume and commodity classification of the cargo.

    Invariant: neither the weight nor the volume can be negative. The stricter
    "weight must be greater than zero" rule belongs to the *finalize manifest*
    use case, not to the value object itself.
    """

    total_weight_kg: float
    total_volume_cbm: float
    commodity_code: str

    def __post_init__(self) -> None:
        """Validate and normalize the manifest figures."""
        object.__setattr__(
            self,
            "total_weight_kg",
            self._validated_measure(self.total_weight_kg, "total weight (kg)"),
        )
        object.__setattr__(
            self,
            "total_volume_cbm",
            self._validated_measure(self.total_volume_cbm, "total volume (cbm)"),
        )

        if not isinstance(self.commodity_code, str):
            raise InvalidCargoManifestError("The commodity code must be a string.")

        code = self.commodity_code.strip().upper()
        if not code:
            raise InvalidCargoManifestError("The commodity code is required.")
        if len(code) > MAX_COMMODITY_CODE_LENGTH:
            raise InvalidCargoManifestError(
                f"The commodity code cannot exceed {MAX_COMMODITY_CODE_LENGTH} "
                "characters."
            )
        object.__setattr__(self, "commodity_code", code)

    @staticmethod
    def _validated_measure(value: object, label: str) -> float:
        """Return ``value`` as a non-negative float or raise."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise InvalidCargoManifestError(f"The {label} must be a number.")
        if value < 0:
            raise InvalidCargoManifestError(f"The {label} cannot be negative.")
        return float(value)

    @staticmethod
    def from_columns(
        total_weight_kg: float | None,
        total_volume_cbm: float | None,
        commodity_code: str | None,
    ) -> "CargoManifest | None":
        """Rebuild the manifest from its columns (SQLAlchemy composite factory).

        A row where every manifest column is ``NULL`` means the shipment has no
        manifest yet, so ``None`` is returned instead of an invalid value object.
        """
        has_no_manifest = (
            total_weight_kg is None
            and total_volume_cbm is None
            and commodity_code is None
        )
        if has_no_manifest:
            return None
        return CargoManifest(
            total_weight_kg=total_weight_kg,  # type: ignore[arg-type]
            total_volume_cbm=total_volume_cbm,  # type: ignore[arg-type]
            commodity_code=commodity_code,  # type: ignore[arg-type]
        )

    def __composite_values__(self) -> tuple[float, float, str]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.total_weight_kg, self.total_volume_cbm, self.commodity_code)

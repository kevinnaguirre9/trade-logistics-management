"""Shipment aggregate root."""

from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.events import ShipmentManifestFinalized
from modules.shipment.src.domain.exceptions import (
    InvalidCargoManifestError,
    ManifestNotFinalizableError,
    RouteNotModifiableError,
)
from modules.shipment.src.domain.value_objects import (
    CargoManifest,
    ShipmentId,
    ShipmentRoute,
    WaybillNumber,
)

#: Once customs or the carrier have taken over, the physical route is frozen.
ROUTE_LOCKED_STATUSES = frozenset(
    {
        TrackingStatus.AWAITING_CUSTOMS_RELEASE,
        TrackingStatus.IN_TRANSIT,
        TrackingStatus.DELIVERED,
    }
)


class Shipment:
    """Physical lifecycle, route constraints and transport readiness of cargo.

    Pure Python: persistence is attached from the infrastructure layer through
    imperative mapping, so this class knows nothing about SQLAlchemy.
    """

    def __init__(
        self,
        shipment_id: ShipmentId,
        waybill_number: WaybillNumber,
        route: ShipmentRoute,
        status: TrackingStatus,
        manifest: CargoManifest | None = None,
        exception_reason: str | None = None,
    ) -> None:
        self.id = shipment_id
        self.waybill_number = waybill_number
        self.route = route
        self.status = status
        self.manifest = manifest
        self.exception_reason = exception_reason

    @classmethod
    def create(
        cls,
        shipment_id: ShipmentId,
        waybill_number: WaybillNumber,
        origin_port_code: str,
        destination_port_code: str,
    ) -> "Shipment":
        """Open a new shipment in ``Draft`` state.

        The manifest is intentionally left empty: it is declared later by the
        *finalize manifest* use case.
        """
        return cls(
            shipment_id=shipment_id,
            waybill_number=waybill_number,
            route=ShipmentRoute(
                origin_port_code=origin_port_code,
                destination_port_code=destination_port_code,
            ),
            status=TrackingStatus.DRAFT,
        )

    def assign_route(self, new_route: ShipmentRoute) -> None:
        """Replace the planned route with ``new_route``.

        The route can only be redrawn while the shipment is still under our
        control: once it is awaiting customs release, in transit or delivered,
        the physical itinerary is settled. The legs themselves are validated by
        :class:`~modules.shipment.src.domain.value_objects.ShipmentRoute`, which
        cannot be constructed with an illogical sequence.
        """
        if self.status in ROUTE_LOCKED_STATUSES:
            raise RouteNotModifiableError(
                f"The route of a shipment in '{self.status}' state can no "
                "longer be modified."
            )

        self.route = new_route

    def finalize_manifest(self, manifest: CargoManifest) -> ShipmentManifestFinalized:
        """Declare the cargo and make the shipment ready for customs.

        Only a draft can be finalized: past that point the manifest has already
        been handed on, so changing it would contradict what customs was told.

        The weight rule is stricter here than in the value object: a manifest
        may be built with a zero weight, but a shipment cannot be declared
        ready to travel with nothing on board.

        Returns the event to publish. It is returned rather than recorded on
        the aggregate because SQLAlchemy does not call ``__init__`` when it
        loads a row, so a list of pending events would not exist on a shipment
        read back from the database.
        """
        if self.status is not TrackingStatus.DRAFT:
            raise ManifestNotFinalizableError(
                f"The manifest of a shipment in '{self.status}' state cannot "
                "be finalized; only a draft can."
            )

        if manifest.total_weight_kg <= 0:
            raise InvalidCargoManifestError(
                "The total weight must be greater than zero to finalize the manifest."
            )

        self.manifest = manifest
        self.status = TrackingStatus.READY_FOR_MANIFEST

        return ShipmentManifestFinalized(
            shipment_id=str(self.id),
            waybill_number=str(self.waybill_number),
            commodity_code=manifest.commodity_code,
        )

    def __repr__(self) -> str:
        """Return a debugging representation of the aggregate."""
        return (
            f"Shipment(id={self.id}, waybill_number={self.waybill_number}, "
            f"status={self.status})"
        )

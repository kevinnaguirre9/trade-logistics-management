"""Shipment aggregate root."""

from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.exceptions import RouteNotModifiableError
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

    def __repr__(self) -> str:
        """Return a debugging representation of the aggregate."""
        return (
            f"Shipment(id={self.id}, waybill_number={self.waybill_number}, "
            f"status={self.status})"
        )

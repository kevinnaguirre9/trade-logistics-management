"""Unit tests for the Shipment aggregate behavior."""

import pytest

from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.exceptions import (
    InvalidShipmentRouteError,
    RouteNotModifiableError,
)
from modules.shipment.src.domain.shipment import ROUTE_LOCKED_STATUSES, Shipment
from modules.shipment.src.domain.value_objects import (
    ShipmentId,
    ShipmentRoute,
    WaybillNumber,
)


def _shipment() -> Shipment:
    return Shipment.create(
        shipment_id=ShipmentId.generate(),
        waybill_number=WaybillNumber("MUST-0000001"),
        origin_port_code="ESVLC",
        destination_port_code="USNYC",
    )


class TestCreate:
    def test_starts_as_a_draft(self) -> None:
        assert _shipment().status is TrackingStatus.DRAFT

    def test_keeps_the_generated_waybill_number(self) -> None:
        assert _shipment().waybill_number == WaybillNumber("MUST-0000001")

    def test_records_the_requested_route(self) -> None:
        shipment = _shipment()

        assert shipment.route.origin_port_code == "ESVLC"
        assert shipment.route.destination_port_code == "USNYC"
        assert shipment.route.transit_legs == ()

    def test_has_no_manifest_yet(self) -> None:
        assert _shipment().manifest is None

    def test_has_no_exception_reason_yet(self) -> None:
        assert _shipment().exception_reason is None

    def test_rejects_a_route_that_ends_where_it_starts(self) -> None:
        with pytest.raises(InvalidShipmentRouteError):
            Shipment.create(
                shipment_id=ShipmentId.generate(),
                waybill_number=WaybillNumber("MUST-0000001"),
                origin_port_code="ESVLC",
                destination_port_code="ESVLC",
            )


class TestAssignRoute:
    """Behaviour of ``Shipment.assign_route``."""

    def test_replaces_the_route(self) -> None:
        shipment = _shipment()

        shipment.assign_route(
            ShipmentRoute(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
                transit_legs=("MAMIR", "PTLIS"),
            )
        )

        assert shipment.route.transit_legs == ("MAMIR", "PTLIS")
        assert str(shipment.route) == "ESVLC > MAMIR > PTLIS > USNYC"

    @pytest.mark.parametrize(
        "status",
        [
            TrackingStatus.DRAFT,
            TrackingStatus.READY_FOR_MANIFEST,
            TrackingStatus.EXCEPTION_HELD,
        ],
    )
    def test_is_allowed_before_customs_takes_over(self, status: TrackingStatus) -> None:
        shipment = _shipment()
        shipment.status = status

        shipment.assign_route(
            ShipmentRoute(
                origin_port_code="ESBCN",
                destination_port_code="USLAX",
            )
        )

        assert shipment.route.origin_port_code == "ESBCN"

    @pytest.mark.parametrize("status", sorted(ROUTE_LOCKED_STATUSES))
    def test_is_refused_once_the_route_is_settled(self, status: TrackingStatus) -> None:
        shipment = _shipment()
        shipment.status = status
        original_route = shipment.route

        with pytest.raises(RouteNotModifiableError):
            shipment.assign_route(
                ShipmentRoute(
                    origin_port_code="ESBCN",
                    destination_port_code="USLAX",
                )
            )

        assert shipment.route is original_route

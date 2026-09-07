"""Unit tests for the Shipment aggregate behavior."""

import pytest

from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.exceptions import InvalidShipmentRouteError
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId, WaybillNumber


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

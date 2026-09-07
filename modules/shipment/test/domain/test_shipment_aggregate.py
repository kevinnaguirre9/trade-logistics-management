"""Unit tests for the Shipment aggregate behavior."""

import pytest

from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.exceptions import (
    InvalidCargoManifestError,
    InvalidShipmentRouteError,
    ManifestNotFinalizableError,
    RouteNotModifiableError,
)
from modules.shipment.src.domain.shipment import ROUTE_LOCKED_STATUSES, Shipment
from modules.shipment.src.domain.value_objects import (
    CargoManifest,
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


class TestFinalizeManifest:
    """Behaviour of ``Shipment.finalize_manifest``."""

    def test_declares_the_cargo_and_advances_the_status(self) -> None:
        shipment = _shipment()

        event = shipment.finalize_manifest(
            CargoManifest(
                total_weight_kg=1000.0,
                total_volume_cbm=12.5,
                commodity_code="8471",
            )
        )

        assert shipment.status is TrackingStatus.READY_FOR_MANIFEST
        assert shipment.manifest is not None
        assert shipment.manifest.commodity_code == "8471"
        assert event.shipment_id == str(shipment.id)
        assert event.waybill_number == str(shipment.waybill_number)
        assert event.commodity_code == "8471"

    def test_is_refused_once_the_shipment_is_no_longer_a_draft(self) -> None:
        shipment = _shipment()
        shipment.status = TrackingStatus.READY_FOR_MANIFEST

        with pytest.raises(ManifestNotFinalizableError):
            shipment.finalize_manifest(
                CargoManifest(
                    total_weight_kg=1000.0,
                    total_volume_cbm=12.5,
                    commodity_code="8471",
                )
            )

    def test_refuses_a_shipment_with_no_weight(self) -> None:
        shipment = _shipment()

        with pytest.raises(InvalidCargoManifestError):
            shipment.finalize_manifest(
                CargoManifest(
                    total_weight_kg=0.0,
                    total_volume_cbm=12.5,
                    commodity_code="8471",
                )
            )

        assert shipment.status is TrackingStatus.DRAFT
        assert shipment.manifest is None

"""Unit tests for the Shipment value objects."""

from uuid import UUID, uuid4

import pytest

from modules.shipment.src.domain.exceptions import (
    InvalidCargoManifestError,
    InvalidShipmentIdError,
    InvalidShipmentRouteError,
    InvalidWaybillNumberError,
)
from modules.shipment.src.domain.value_objects import (
    CargoManifest,
    ShipmentId,
    ShipmentRoute,
    WaybillNumber,
)


class TestShipmentId:
    def test_generates_a_unique_identifier(self) -> None:
        assert ShipmentId.generate() != ShipmentId.generate()

    def test_accepts_a_uuid_string(self) -> None:
        raw = uuid4()

        assert ShipmentId(str(raw)).value == raw

    def test_is_compared_by_value(self) -> None:
        raw = uuid4()

        assert ShipmentId(raw).equals(ShipmentId(raw))

    def test_rejects_a_malformed_identifier(self) -> None:
        with pytest.raises(InvalidShipmentIdError):
            ShipmentId("not-a-uuid")

    def test_exposes_its_column_value(self) -> None:
        raw = uuid4()

        assert ShipmentId(raw).__composite_values__() == (raw,)


class TestWaybillNumber:
    def test_accepts_the_carrier_format(self) -> None:
        assert WaybillNumber("MUST-0000042").value == "MUST-0000042"

    def test_is_built_from_a_serial(self) -> None:
        assert WaybillNumber.from_serial(42).value == "MUST-0000042"

    def test_normalizes_case_and_whitespace(self) -> None:
        assert WaybillNumber(" must-0000042 ").equals(WaybillNumber("MUST-0000042"))

    @pytest.mark.parametrize(
        "raw",
        ["MUST-42", "MUST-00000042", "OTHER-0000042", "0000042", ""],
    )
    def test_rejects_anything_else(self, raw: str) -> None:
        with pytest.raises(InvalidWaybillNumberError):
            WaybillNumber(raw)

    def test_exposes_its_column_value(self) -> None:
        assert WaybillNumber("MUST-0000042").__composite_values__() == (
            "MUST-0000042",
        )


class TestCargoManifest:
    def test_normalizes_its_figures(self) -> None:
        manifest = CargoManifest(1200, 8.5, " 8703.23 ")

        assert manifest.total_weight_kg == 1200.0
        assert manifest.total_volume_cbm == 8.5
        assert manifest.commodity_code == "8703.23"

    @pytest.mark.parametrize(
        ("weight", "volume"),
        [(-1.0, 8.5), (1200.0, -0.1)],
    )
    def test_rejects_negative_figures(self, weight: float, volume: float) -> None:
        with pytest.raises(InvalidCargoManifestError):
            CargoManifest(weight, volume, "8703.23")

    def test_rejects_a_missing_commodity_code(self) -> None:
        with pytest.raises(InvalidCargoManifestError):
            CargoManifest(1200.0, 8.5, "   ")

    def test_is_absent_when_every_column_is_null(self) -> None:
        assert CargoManifest.from_columns(None, None, None) is None

    def test_is_rebuilt_from_its_columns(self) -> None:
        assert CargoManifest.from_columns(1200.0, 8.5, "8703.23") == CargoManifest(
            1200.0, 8.5, "8703.23"
        )


class TestShipmentRoute:
    def test_normalizes_the_port_codes(self) -> None:
        route = ShipmentRoute(" esvlc ", "usnyc")

        assert route.origin_port_code == "ESVLC"
        assert route.destination_port_code == "USNYC"

    def test_starts_without_transit_legs(self) -> None:
        assert ShipmentRoute("ESVLC", "USNYC").transit_legs == ()

    def test_keeps_the_transit_legs_ordered_and_immutable(self) -> None:
        route = ShipmentRoute("ESVLC", "USNYC", ["mamir", "PAONX"])

        assert route.transit_legs == ("MAMIR", "PAONX")

    def test_rejects_a_round_trip(self) -> None:
        with pytest.raises(InvalidShipmentRouteError):
            ShipmentRoute("ESVLC", "esvlc")

    @pytest.mark.parametrize("code", ["ES", "ESVLCX", "E5VLC", "12345"])
    def test_rejects_a_malformed_port_code(self, code: str) -> None:
        with pytest.raises(InvalidShipmentRouteError):
            ShipmentRoute(code, "USNYC")

    def test_rejects_a_malformed_transit_leg(self) -> None:
        with pytest.raises(InvalidShipmentRouteError):
            ShipmentRoute("ESVLC", "USNYC", ["NOPE"])

    def test_exposes_its_column_values(self) -> None:
        route = ShipmentRoute("ESVLC", "USNYC", ["MAMIR"])

        assert route.__composite_values__() == ("ESVLC", "USNYC", ["MAMIR"])

    def test_reads_as_a_sequence_of_hops(self) -> None:
        route = ShipmentRoute("ESVLC", "USNYC", ["MAMIR"])

        assert str(route) == "ESVLC > MAMIR > USNYC"


def test_shipment_id_wraps_a_uuid_instance() -> None:
    assert isinstance(ShipmentId.generate().value, UUID)
